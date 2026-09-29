"""Los 8 comandos de la rama de julio, rehechos sobre main (sprint de pendientes
2026-09-28).

El commit `36317d44` (rama `agent/mcp-despacho`) traía las Olas 2 y 3 CUI y
nunca se mergeó. Aquí se rehacen sobre el código de hoy y se prueba lo que de
verdad importa de cada uno:

* que esté en los TRES lugares (ejecutor, catálogo, prompt) y que la capacidad
  de propuesta del chat salga sola del catálogo;
* que `comandos_para` lo ofrezca SÓLO a quien tiene el permiso — y con la
  acción que pide la pantalla, no una más floja;
* que el ejecutor re-chequee el permiso aunque el LLM lo proponga (defensa en
  profundidad, §4 #20);
* y la regla de negocio de cada uno: una factura cobrada no se cancela, un
  movimiento contable automático no se anula a mano, el Catálogo se edita por
  lista blanca.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

#: tipo → (módulo, acción) que tiene que tener quien lo pida. Es la MISMA acción
#: que gatea la pantalla equivalente.
PERMISO_DE = {
    "crear_factura_desde_cotizacion": ("facturacion", "crear"),
    "cancelar_factura": ("facturacion", "cancelar"),
    "duplicar_factura": ("facturacion", "crear"),
    "ligar_factura_proyecto": ("facturacion", "crear"),
    "anular_cotizacion": ("cotizaciones", "anular"),
    "anular_asiento": ("contaduria", "anular"),
    "actualizar_proveedor": ("catalogo", "gestionar_categorias"),
    "actualizar_variacion": ("catalogo", "editar"),
}
NUEVOS = set(PERMISO_DE)


@pytest.fixture(autouse=True)
def _on_commit_inmediato(monkeypatch):
    """Bug E §14: los signals de Contaduría corren en `on_commit`."""
    from django.db import transaction as _tx
    monkeypatch.setattr(_tx, "on_commit", lambda fn, using=None, robust=False: fn())


# ── Ayudantes ───────────────────────────────────────────────────────────────

def _accion(payload):
    return SimpleNamespace(payload=payload)


def _ejecutar(tipo, payload, usuario, contexto=None):
    from apps.el_dictado.ejecutores import EJECUTORES
    accion = _accion(payload)
    EJECUTORES[tipo](accion, usuario, contexto or {})
    return accion


def _con_permisos(usuario_factory, *pares):
    """Un «miembro» (sin defaults) con SÓLO los permisos dados. Se conceden
    antes de usarlo: el caché de permisos vive en la instancia."""
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="miembro")
    for modulo, accion in pares:
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo=modulo, permiso=accion, defaults={"activo": True})
    return u


def _factura(cli, autor, **kw):
    from apps.facturacion.models import Factura, FacturaItem
    fac = Factura.objects.create(cliente=cli, titulo=kw.pop("titulo", "Factura test"),
                                 creado_por=autor, **kw)
    FacturaItem.objects.create(factura=fac, orden=0, descripcion="X",
                               cantidad=Decimal("1"), precio_unitario=Decimal("1000.00"))
    return fac


def _cotizacion(cli, autor, **kw):
    from apps.cotizaciones.models import Cotizacion, CotizacionItem
    cot = Cotizacion.objects.create(cliente=cli, titulo="Cot test", creado_por=autor, **kw)
    CotizacionItem.objects.create(cotizacion=cot, orden=0, descripcion="Playera",
                                  cantidad=Decimal("10"), precio_unitario=Decimal("100.00"))
    return cot


def _asiento(autor, **kw):
    from apps.contaduria import services
    return services.crear_asiento(
        descripcion="Movimiento de prueba",
        partidas=[{"cuenta": "1.1.02", "cargo": Decimal("500.00")},
                  {"cuenta": "4.1.01", "abono": Decimal("500.00")}],
        creado_por=autor, **kw,
    )


def _servicio_con_variacion(autor):
    from apps.el_catalogo.models import CategoriaServicio, Servicio, Variacion
    cat, _ = CategoriaServicio.objects.get_or_create(nombre="Producción", defaults={"orden": 10})
    srv = Servicio.objects.create(nombre="Playera Olas", precio_base="120.00",
                                  categoria=cat, creado_por=autor)
    var = Variacion.objects.create(servicio=srv, nombre="Talla M", costo=Decimal("70.00"))
    return srv, var


# ── 1. Los tres lugares + la capacidad de propuesta ─────────────────────────

def test_cada_comando_esta_en_los_tres_lugares():
    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO

    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    catalogo = {c["tipo"]: c for c in COMANDOS_DICTADO}
    for tipo in NUEVOS:
        assert tipo in EJECUTORES, f"{tipo}: falta el ejecutor"
        assert tipo in catalogo, f"{tipo}: falta en el catálogo"
        assert catalogo[tipo].get("gating"), f"{tipo}: sin gating se le ofrece a todos"
        assert f"- {tipo}:" in prompt, f"{tipo}: falta su payload en el prompt"


def test_el_chat_los_recibe_como_propuesta_sin_tocarlo():
    """El chat y el registro MCP se derivan del catálogo: basta con registrarlos
    ahí para que El Chalán los pueda PROPONER (nunca los aplica solo, §20)."""
    import capacidades
    for tipo in NUEVOS:
        cap = capacidades.CAPACIDADES.get(tipo)
        assert cap is not None, f"{tipo}: no llegó al registro de capacidades"
        assert cap.modo == capacidades.MODO_PROPUESTA


# ── 2. Se ofrecen SÓLO a quien tiene el permiso ─────────────────────────────

@pytest.mark.parametrize("tipo", sorted(NUEVOS))
def test_comandos_para_lo_ofrece_solo_con_su_permiso(tipo, usuario_factory):
    import capacidades
    from lib.dictado_catalogo import comandos_para

    con = _con_permisos(usuario_factory, PERMISO_DE[tipo])
    sin = _con_permisos(usuario_factory)
    assert tipo in {c["tipo"] for c in comandos_para(con)}
    assert tipo not in {c["tipo"] for c in comandos_para(sin)}
    # El chat usa el mismo gate que el Dictado.
    assert tipo in {s["nombre"] for s in capacidades.specs_chat(con, modos=("propuesta",))}
    assert tipo not in {s["nombre"] for s in capacidades.specs_chat(sin, modos=("propuesta",))}


def test_crear_facturas_no_alcanza_para_cancelarlas(usuario_factory):
    """Cancelar tiene su acción propia; poder crear no la concede."""
    from lib.dictado_catalogo import comandos_para
    u = _con_permisos(usuario_factory, ("facturacion", "crear"))
    tipos = {c["tipo"] for c in comandos_para(u)}
    assert "duplicar_factura" in tipos
    assert "cancelar_factura" not in tipos


def test_editar_productos_no_alcanza_para_editar_proveedores(usuario_factory):
    """La ficha del proveedor en pantalla pide `gestionar_categorias`, no
    `editar`: dictando se pide lo mismo."""
    from lib.dictado_catalogo import comandos_para
    u = _con_permisos(usuario_factory, ("catalogo", "editar"))
    tipos = {c["tipo"] for c in comandos_para(u)}
    assert "actualizar_variacion" in tipos
    assert "actualizar_proveedor" not in tipos


def test_super_admin_los_ve_todos_y_el_disenador_ninguno(usuario_factory):
    from lib.dictado_catalogo import comandos_para
    admin = usuario_factory(rol="super_admin")
    disenador = usuario_factory(rol="disenador")
    assert {c["tipo"] for c in comandos_para(admin)} >= NUEVOS
    assert not (NUEVOS & {c["tipo"] for c in comandos_para(disenador)})


# ── 3. El ejecutor re-chequea el permiso (defensa en profundidad) ───────────

def test_sin_permiso_ningun_ejecutor_toca_la_base(usuario_factory, cliente_factory,
                                                    proyecto_factory):
    """Aunque el LLM proponga la acción con un payload perfecto, un usuario sin
    el permiso no escribe nada."""
    from apps.contaduria.models import Asiento
    from apps.cotizaciones.models import Cotizacion
    from apps.el_catalogo.models import Proveedor
    from apps.facturacion.models import Factura

    admin = usuario_factory(rol="super_admin")
    intruso = _con_permisos(usuario_factory)
    cli = cliente_factory(creado_por=admin)
    cot = _cotizacion(cli, admin)
    fac = _factura(cli, admin)
    proyecto = proyecto_factory(cliente=cli, creado_por=admin)
    asiento = _asiento(admin)
    prov = Proveedor.objects.create(razon_social="Telas Intocables", creado_por=admin)
    _srv, var = _servicio_con_variacion(admin)
    facturas_antes = Factura.objects.count()

    casos = {
        "crear_factura_desde_cotizacion": {"codigo": cot.codigo},
        "cancelar_factura": {"codigo": fac.codigo, "motivo": "x"},
        "duplicar_factura": {"codigo": fac.codigo},
        "ligar_factura_proyecto": {"codigo": fac.codigo, "proyecto_slug": proyecto.slug},
        "anular_cotizacion": {"codigo": cot.codigo, "motivo": "x"},
        "anular_asiento": {"codigo": asiento.codigo, "motivo": "x"},
        "actualizar_proveedor": {"proveedor": prov.razon_social, "telefono": "555"},
        "actualizar_variacion": {"variacion_id": var.pk, "costo": "1"},
    }
    assert set(casos) == NUEVOS
    for tipo, payload in casos.items():
        with pytest.raises(ValueError, match="permiso"):
            _ejecutar(tipo, payload, intruso)

    assert Factura.objects.count() == facturas_antes
    fac.refresh_from_db()
    assert fac.estado == "borrador" and fac.proyecto_id is None
    assert Cotizacion.objects.get(pk=cot.pk).estado != "anulada"
    assert Asiento.objects.get(pk=asiento.pk).anulado is False
    prov.refresh_from_db()
    var.refresh_from_db()
    assert prov.telefono == "" and var.costo == Decimal("70.00")


# ── 4. Facturación ───────────────────────────────────────────────────────────

def test_crear_factura_desde_cotizacion(usuario_factory, cliente_factory):
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    accion = _ejecutar("crear_factura_desde_cotizacion", {"codigo": cot.codigo.lower()}, admin)
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert accion.entidad_tipo == "factura"
    assert fac.cotizacion_origen_id == cot.pk and fac.estado == "borrador"
    assert fac.items.count() == 1


def test_facturar_no_cobra_las_alternativas_de_volumen(usuario_factory, cliente_factory):
    """Una escala que el cliente puede escoger va en la cotización como línea
    INFORMATIVA y no suma a su total. La factura no tiene esa bandera: si la
    copiara, cobraría las alternativas."""
    from apps.cotizaciones.models import CotizacionItem
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    CotizacionItem.objects.create(cotizacion=cot, orden=1, descripcion="100 pz (B)",
                                  cantidad=Decimal("100"), precio_unitario=Decimal("90.00"),
                                  agrupado=True, informativo=True)
    accion = _ejecutar("crear_factura_desde_cotizacion", {"codigo": cot.codigo}, admin)
    fac = Factura.objects.get(pk=accion.entidad_id)
    assert fac.items.count() == 1
    assert (fac.calcular_totales()["subtotal_items"]
            == cot.calcular_totales()["subtotal_items"])



def test_sustituir_lineas_tampoco_trae_las_alternativas(client, usuario_factory, cliente_factory):
    """El botón «Sustituir» del form de factura pide las líneas por JSON: la
    misma regla que al facturar desde la cotización."""
    from apps.cotizaciones.models import CotizacionItem
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    CotizacionItem.objects.create(cotizacion=cot, orden=1, descripcion="100 pz (B)",
                                  cantidad=Decimal("100"), precio_unitario=Decimal("90.00"),
                                  agrupado=True, informativo=True)
    client.force_login(admin)
    resp = client.get(f"/facturacion/api/cotizacion/{cot.pk}/datos/")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert "100 pz (B)" not in {i["descripcion"] for i in items}

def test_no_se_factura_una_cotizacion_anulada(usuario_factory, cliente_factory):
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin, estado="anulada")
    with pytest.raises(ValueError, match="anulada"):
        _ejecutar("crear_factura_desde_cotizacion", {"codigo": cot.codigo}, admin)
    assert not Factura.objects.filter(cotizacion_origen=cot).exists()


def test_cancelar_factura_por_su_folio(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin)
    _ejecutar("cancelar_factura", {"codigo": f"F-{fac.folio_numero}",
                                   "motivo": "captura duplicada"}, admin)
    fac.refresh_from_db()
    assert fac.estado == "cancelada"
    assert fac.motivo_cancelacion == "captura duplicada"


def test_cancelar_factura_pide_motivo(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin)
    with pytest.raises(ValueError, match="motivo"):
        _ejecutar("cancelar_factura", {"codigo": fac.codigo}, admin)
    fac.refresh_from_db()
    assert fac.estado != "cancelada"


def test_una_factura_cobrada_no_se_cancela_y_dice_que_hacer(usuario_factory, cliente_factory):
    """`cancelar_factura_cobrada` sigue prohibido. El error nombra el ingreso
    que hay que anular primero, para que El Chalán lo pueda proponer."""
    from apps.tesoreria.models import Ingreso
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    fac = _factura(cli, admin)
    cobro = Ingreso.objects.create(monto=Decimal("500.00"), descripcion="Cobro",
                                   fecha=dt.date.today(), metodo="transferencia",
                                   cliente=cli, factura=fac, creado_por=admin)
    with pytest.raises(ValueError) as exc:
        _ejecutar("cancelar_factura", {"codigo": fac.codigo, "motivo": "x"}, admin)
    mensaje = str(exc.value)
    assert cobro.codigo in mensaje
    assert "anula" in mensaje.lower()
    fac.refresh_from_db()
    assert fac.estado != "cancelada"
    cobro.refresh_from_db()
    assert cobro.anulado is False, "no se anulan cobros en silencio"


def test_duplicar_factura(usuario_factory, cliente_factory):
    from apps.facturacion.models import Factura
    admin = usuario_factory(rol="super_admin")
    fac = _factura(cliente_factory(creado_por=admin), admin, titulo="Original")
    accion = _ejecutar("duplicar_factura", {"codigo": fac.codigo}, admin)
    nueva = Factura.objects.get(pk=accion.entidad_id)
    assert nueva.pk != fac.pk and nueva.estado == "borrador"
    assert nueva.items.count() == 1
    assert nueva.titulo == "Copia de Original"


def test_ligar_factura_por_folio_al_codigo_del_proyecto(usuario_factory, cliente_factory,
                                                        proyecto_factory):
    """La gente dicta «la F-106 al LC-0044», no el código interno ni el slug."""
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    fac = _factura(cli, admin)
    proyecto = proyecto_factory(cliente=cli, creado_por=admin, nombre="Gorras Olas")
    _ejecutar("ligar_factura_proyecto",
              {"codigo": f"F{fac.folio_numero}", "proyecto_slug": proyecto.codigo}, admin)
    fac.refresh_from_db()
    assert fac.proyecto_id == proyecto.pk


def test_no_se_liga_una_factura_cancelada_ni_dos_veces(usuario_factory, cliente_factory,
                                                       proyecto_factory):
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    proyecto = proyecto_factory(cliente=cli, creado_por=admin)
    cancelada = _factura(cli, admin, estado="cancelada")
    with pytest.raises(ValueError, match="cancelada"):
        _ejecutar("ligar_factura_proyecto",
                  {"codigo": cancelada.codigo, "proyecto_slug": proyecto.slug}, admin)
    ligada = _factura(cli, admin, proyecto=proyecto)
    with pytest.raises(ValueError, match="ya está ligada"):
        _ejecutar("ligar_factura_proyecto",
                  {"codigo": ligada.codigo, "proyecto_slug": proyecto.slug}, admin)


def test_el_boton_ligar_usa_el_mismo_service(client, usuario_factory, cliente_factory,
                                            proyecto_factory):
    """Refactor DRY: la vista del proyecto y El Chalán ligan por el mismo
    camino (y la vista ya no truena con una factura ligada de antes)."""
    admin = usuario_factory(rol="super_admin")
    cli = cliente_factory(creado_por=admin)
    proyecto = proyecto_factory(cliente=cli, creado_por=admin)
    fac = _factura(cli, admin)
    client.force_login(admin)
    resp = client.post(f"/facturacion/ligar/{proyecto.pk}/", {"factura": fac.pk},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code in (200, 204)
    fac.refresh_from_db()
    assert fac.proyecto_id == proyecto.pk
    resp = client.post(f"/facturacion/ligar/{proyecto.pk}/", {"factura": fac.pk},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert "ya está ligada" in resp.content.decode()


# ── 5. Anular ────────────────────────────────────────────────────────────────

def test_anular_cotizacion(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    _ejecutar("anular_cotizacion", {"codigo": cot.codigo, "motivo": "el cliente desistió"}, admin)
    cot.refresh_from_db()
    assert cot.estado == "anulada"
    assert cot.motivo_anulacion == "el cliente desistió"


def test_anular_cotizacion_pide_motivo_y_no_se_anula_dos_veces(usuario_factory, cliente_factory):
    admin = usuario_factory(rol="super_admin")
    cot = _cotizacion(cliente_factory(creado_por=admin), admin)
    with pytest.raises(ValueError, match="motivo"):
        _ejecutar("anular_cotizacion", {"codigo": cot.codigo}, admin)
    _ejecutar("anular_cotizacion", {"codigo": cot.codigo, "motivo": "x"}, admin)
    with pytest.raises(ValueError, match="ya estaba anulada"):
        _ejecutar("anular_cotizacion", {"codigo": cot.codigo, "motivo": "otra vez"}, admin)


def test_anular_un_movimiento_capturado_a_mano(usuario_factory):
    admin = usuario_factory(rol="super_admin")
    asiento = _asiento(admin)
    _ejecutar("anular_asiento", {"codigo": asiento.codigo, "motivo": "captura duplicada"}, admin)
    asiento.refresh_from_db()
    assert asiento.anulado is True
    assert asiento.motivo_anulacion == "captura duplicada"


@pytest.mark.parametrize("origen,palabra", [
    ("auto_ingreso", "sistema"),
    ("auto_factura_emitida", "sistema"),
    ("cierre", "cierre"),
])
def test_un_movimiento_automatico_no_se_anula_por_dictado(origen, palabra, usuario_factory):
    """El reverso automático busca el asiento original VIGENTE: anularlo a mano
    dejaría la contabilidad descuadrada en silencio. Se corrige en su origen."""
    admin = usuario_factory(rol="super_admin")
    asiento = _asiento(admin, origen=origen, referencia_externa=f"prueba:{origen}")
    with pytest.raises(ValueError, match=palabra):
        _ejecutar("anular_asiento", {"codigo": asiento.codigo, "motivo": "x"}, admin)
    asiento.refresh_from_db()
    assert asiento.anulado is False


def test_el_error_del_automatico_nombra_su_documento(usuario_factory, cliente_factory):
    """Un ingreso deja su asiento automático; el error dice cuál es, para que
    El Chalán proponga anular ESE ingreso."""
    from apps.contaduria.models import Asiento
    from apps.tesoreria.models import Ingreso
    admin = usuario_factory(rol="super_admin")
    ing = Ingreso.objects.create(monto=Decimal("800.00"), descripcion="Venta",
                                 fecha=dt.date.today(), metodo="transferencia",
                                 cliente=cliente_factory(creado_por=admin), creado_por=admin)
    asiento = Asiento.objects.filter(referencia_externa=f"tesoreria.ingreso:{ing.pk}").first()
    assert asiento is not None, "el signal de Contaduría no generó el asiento"
    with pytest.raises(ValueError) as exc:
        _ejecutar("anular_asiento", {"codigo": asiento.codigo, "motivo": "x"}, admin)
    assert ing.codigo in str(exc.value)


# ── 6. Editar el Catálogo ────────────────────────────────────────────────────

def test_actualizar_proveedor(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    accion = _ejecutar("actualizar_proveedor",
                       {"proveedor": "telas del norte", "telefono": "555-9090",
                        "rfc": "tdn010101abc"}, admin)
    prov.refresh_from_db()
    assert prov.telefono == "555-9090" and prov.rfc == "TDN010101ABC"
    assert accion.entidad_tipo == "proveedor" and accion.entidad_id == prov.pk


def test_la_direccion_arrastra_la_fiscal_si_es_la_misma(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    admin = usuario_factory(rol="super_admin")
    igual = Proveedor.objects.create(razon_social="Bordados Uno", creado_por=admin,
                                     fiscal_igual=True)
    distinta = Proveedor.objects.create(razon_social="Bordados Dos", creado_por=admin,
                                        fiscal_igual=False, direccion_fiscal="Fiscal 1")
    _ejecutar("actualizar_proveedor", {"proveedor": "Bordados Uno", "direccion": "Calle 2"}, admin)
    _ejecutar("actualizar_proveedor", {"proveedor": "Bordados Dos", "direccion": "Calle 3"}, admin)
    igual.refresh_from_db()
    distinta.refresh_from_db()
    assert igual.direccion == igual.direccion_fiscal == "Calle 2"
    assert distinta.direccion == "Calle 3" and distinta.direccion_fiscal == "Fiscal 1"


def test_nombrar_al_proveedor_con_razon_social_no_lo_renombra(usuario_factory):
    """El LLM identifica al proveedor como en `crear_proveedor`. Sin
    `proveedor`, esa razón social dice A QUIÉN se edita; renombrar se pide con
    `razon_social_nueva` o dentro de `campos`."""
    from apps.el_catalogo.models import Proveedor
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    _ejecutar("actualizar_proveedor", {"razon_social": "telas del norte", "telefono": "7"}, admin)
    prov.refresh_from_db()
    assert prov.razon_social == "Telas del Norte" and prov.telefono == "7"
    _ejecutar("actualizar_proveedor",
              {"proveedor": "Telas del Norte", "razon_social_nueva": "Telas Norteñas"}, admin)
    prov.refresh_from_db()
    assert prov.razon_social == "Telas Norteñas"
    _ejecutar("actualizar_proveedor",
              {"razon_social": "Telas Norteñas", "campos": {"razon_social": "TN Textiles"}}, admin)
    prov.refresh_from_db()
    assert prov.razon_social == "TN Textiles"



def test_el_prompt_y_el_catalogo_ensenan_a_renombrar_con_la_llave_que_se_entiende():
    """Renombrar un proveedor es `razon_social_nueva`: si el prompt o el
    catálogo le enseñaran al LLM a mandar `razon_social`, el ejecutor lo
    tomaría como A QUIÉN editar y el cambio de nombre se perdería en silencio."""
    from lib.dictado_catalogo import COMANDOS_DICTADO
    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    linea = next(renglon for renglon in prompt.splitlines()
                 if renglon.startswith("- actualizar_proveedor:"))
    assert "razon_social_nueva" in linea
    assert "razon_social?" not in linea
    catalogo = next(c for c in COMANDOS_DICTADO if c["tipo"] == "actualizar_proveedor")
    assert "razon_social_nueva" in catalogo["payload"]
    assert "razon_social?" not in catalogo["payload"]

def test_actualizar_proveedor_rechaza_lo_que_no_sirve(usuario_factory):
    from apps.el_catalogo.models import Proveedor
    admin = usuario_factory(rol="super_admin")
    Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    Proveedor.objects.create(razon_social="Telas del Sur", creado_por=admin)
    with pytest.raises(ValueError, match="cambiar"):
        _ejecutar("actualizar_proveedor", {"proveedor": "Telas del Norte"}, admin)
    with pytest.raises(ValueError, match="correo"):
        _ejecutar("actualizar_proveedor",
                  {"proveedor": "Telas del Norte", "email_contacto": "no-es-correo"}, admin)
    with pytest.raises(ValueError, match="Varios"):
        _ejecutar("actualizar_proveedor", {"proveedor": "Telas", "telefono": "1"}, admin)


def test_actualizar_proveedor_no_toca_lo_que_no_esta_en_la_lista(usuario_factory):
    """Lista blanca: archivar o re-colgar qué surte no se hace dictando."""
    from apps.el_catalogo.models import Proveedor
    admin = usuario_factory(rol="super_admin")
    prov = Proveedor.objects.create(razon_social="Telas del Norte", creado_por=admin)
    _ejecutar("actualizar_proveedor",
              {"proveedor": "Telas del Norte", "telefono": "1", "activo": False,
               "creado_por": None}, admin)
    prov.refresh_from_db()
    assert prov.activo is True and prov.creado_por_id == admin.pk


def test_actualizar_variacion_por_id(usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _srv, var = _servicio_con_variacion(admin)
    accion = _ejecutar("actualizar_variacion", {"variacion_id": var.pk, "costo": "90"}, admin)
    var.refresh_from_db()
    assert var.costo == Decimal("90.00")
    assert accion.entidad_tipo == "variacion"


def test_actualizar_variacion_por_producto_y_nombre(usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _srv, var = _servicio_con_variacion(admin)
    _ejecutar("actualizar_variacion",
              {"servicio": "Playera Olas", "variacion": "talla m", "disponible": False}, admin)
    var.refresh_from_db()
    assert var.disponible is False


def test_actualizar_variacion_rechaza_costo_negativo(usuario_factory):
    admin = usuario_factory(rol="super_admin")
    _srv, var = _servicio_con_variacion(admin)
    with pytest.raises(ValueError, match="negativo"):
        _ejecutar("actualizar_variacion", {"variacion_id": var.pk, "costo": "-5"}, admin)
    var.refresh_from_db()
    assert var.costo == Decimal("70.00")


# ── 7. Lo que se ve en el chat ──────────────────────────────────────────────

def test_la_tarjeta_de_la_propuesta_nombra_el_documento():
    """Sin la etiqueta, «Cancelar factura» salía sin decir CUÁL."""
    from apps.el_dictado.presentacion import campos_accion, resumen_accion
    payload = {"codigo": "F-106", "motivo": "capturada dos veces"}
    assert resumen_accion("cancelar_factura", payload) == "F-106"
    etiquetas = {c["etiqueta"]: c["valor"] for c in campos_accion("cancelar_factura", payload)}
    assert etiquetas["Documento"] == "F-106"
    assert etiquetas["Motivo"] == "capturada dos veces"
