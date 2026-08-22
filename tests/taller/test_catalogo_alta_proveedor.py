"""Catálogo · alta de producto y ficha (sprint 2026-08-22, notas 2·3·4·10·11).

El flujo de captura estaba a medias y por eso fallaban tres cosas que parecían
distintas: el atajo rápido creaba el producto **sin proveedor**, y sin proveedor
no hay calculadora (su gating pregunta por la M2M) ni proveedor principal.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = [pytest.mark.django_db, pytest.mark.taller]

RUTA_JS_TARJETA = "el-taller/templates/proyectos/_form_productos_js.html"
RUTA_FICHA = "el-taller/templates/catalogo/form.html"


def _raiz():
    """Raíz del repo (los tests corren desde `el-taller/`)."""
    import pathlib
    aqui = pathlib.Path(__file__).resolve()
    for padre in aqui.parents:
        if (padre / RUTA_JS_TARJETA).exists():
            return padre
    raise AssertionError("no encontré la raíz del repo")


def _cat():
    from apps.el_catalogo.models import CategoriaServicio
    return CategoriaServicio.objects.create(nombre="Cat alta", orden=1)


def _prov(razon="Maracas Don José", activo=True):
    from apps.el_catalogo.models import Proveedor
    return Proveedor.objects.create(razon_social=razon, activo=activo)


# ── Nota 2 · proveedor en el alta rápida ────────────────────────────────────

def test_atajo_crea_el_producto_con_sus_proveedores(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat, p1, p2 = _cat(), _prov("Alfa Textiles"), _prov("Zeta Bordados")
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post("/catalogo/quick-create/", {
        "nombre": "Playera del atajo", "categoria_id": cat.pk,
        "precio_base": "150", "costo": "60",
        # Ojo con el ORDEN: Zeta va primero a propósito. `Proveedor.Meta.ordering`
        # es alfabético, así que «el primero de la M2M» no es «el primero que
        # marcaste» — el principal debe ser Zeta.
        "proveedores": [str(p2.pk), str(p1.pk)],
    })
    assert r.status_code == 200
    data = json.loads(r.content)
    assert data["ok"] is True
    srv = Servicio.objects.get(pk=data["id"])
    assert set(srv.proveedores.values_list("pk", flat=True)) == {p1.pk, p2.pk}
    assert srv.proveedor_principal_id == p2.pk
    # El JSON los devuelve para que el JS pinte la etiqueta.
    assert [d["id"] for d in data["proveedores"]] == [p2.pk, p1.pk]
    assert data["proveedor_id"] == str(p2.pk)
    assert data["proveedor"] == "Zeta Bordados"


def test_atajo_ignora_proveedor_archivado_o_inventado(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    bueno = _prov("Vigente SA")
    archivado = _prov("Archivado SA", activo=False)
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post("/catalogo/quick-create/", {
        "nombre": "Producto filtrado", "categoria_id": cat.pk, "precio_base": "10",
        "proveedores": [str(archivado.pk), "999999", "no-soy-un-id", str(bueno.pk)],
    })
    assert r.status_code == 200
    srv = Servicio.objects.get(pk=json.loads(r.content)["id"])
    # Nunca se confía en los ids del cliente: sólo sobrevive el activo real.
    assert list(srv.proveedores.values_list("pk", flat=True)) == [bueno.pk]
    assert srv.proveedor_principal_id == bueno.pk


def test_atajo_sin_proveedores_sigue_funcionando(client, usuario_factory):
    """Back-compat: el atajo se puede usar igual que antes (nota: sin proveedor
    el producto queda incompleto, pero NO debe fallar)."""
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post("/catalogo/quick-create/", {
        "nombre": "Pelón", "categoria_id": cat.pk, "precio_base": "10",
    })
    assert r.status_code == 200
    srv = Servicio.objects.get(pk=json.loads(r.content)["id"])
    assert srv.proveedores.count() == 0
    assert srv.proveedor_principal_id is None


def test_los_cuatro_paneles_del_atajo_piden_proveedor():
    """Los 4 lugares que consumen el atajo incluyen el selector y mandan los ids."""
    raiz = _raiz()
    paneles = {
        "el-taller/templates/proyectos/form.html": "qc",
        "el-taller/templates/proyectos/detalle.html": "qc",
        "el-taller/templates/proyectos/_modal_agregar_producto.html": "qcp",
        "el-taller/templates/cotizaciones/form.html": "cot-qc",
    }
    for ruta, prefijo in paneles.items():
        html = (raiz / ruta).read_text()
        assert "catalogo/_qc_proveedores.html" in html, ruta
        assert f'prefijo="{prefijo}"' in html, ruta
    # Y los 3 sitios que arman el `fetch` mandan `proveedores`.
    for ruta, prefijo in [
        (RUTA_JS_TARJETA, "qc"),
        ("el-taller/templates/proyectos/_modal_agregar_producto.html", "qcp"),
        ("el-taller/templates/cotizaciones/form.html", "cot-qc"),
    ]:
        js = (raiz / ruta).read_text()
        assert f"qcProvIds('{prefijo}')" in js, ruta
        assert "'proveedores'" in js, ruta


# ── Trampa · guardar la ficha sin tocar proveedores ─────────────────────────

def test_guardar_ficha_sin_mandar_proveedores_no_los_borra(client, usuario_factory):
    """El form BORRA la M2M si el POST no la manda — se prueba explícitamente
    porque cualquier cambio aquí lo puede reintroducir.

    Contrato real: `proveedores` viaja SIEMPRE en el POST de la ficha (los
    checkboxes viven ocultos justo para eso). Lo que no debe pasar es que un
    guardado normal, con los mismos valores, pierda el vínculo.
    """
    from apps.el_catalogo.models import Servicio
    cat, prov = _cat(), _prov()
    srv = Servicio.objects.create(nombre="Con proveedor", precio_base=Decimal("100"),
                                  categoria=cat, proveedor_principal=prov)
    srv.proveedores.add(prov)
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post(reverse("catalogo-editar", args=[srv.pk]), {
        "nombre": "Con proveedor", "descripcion_default": "", "costo": "0",
        "precio_base": "100", "categoria": str(cat.pk),
        "proveedores": str(prov.pk), "proveedor_principal": str(prov.pk),
    })
    assert r.status_code in (200, 302)
    srv.refresh_from_db()
    assert list(srv.proveedores.values_list("pk", flat=True)) == [prov.pk]
    assert srv.proveedor_principal_id == prov.pk


# ── Nota 3 · la calculadora aparece en cuanto haya proveedor ────────────────

def test_calculadora_se_pinta_en_el_alta_escondida(client, usuario_factory):
    """En el ALTA el recuadro existe (escondido) para que el JS lo revele al
    marcar el proveedor. Antes sólo existía al editar."""
    _cat()
    _prov("Simil Cuero Plymouth")
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("catalogo-nuevo")).content.decode()
    assert "data-calc-box" in html
    assert "data-calc-proveedores" in html
    assert "🧮 Calculadora de costos" in html


def test_calculadora_no_se_pinta_si_no_existe_el_proveedor(client, usuario_factory):
    """Sin el proveedor que la dispara, el recuadro no estorba en el alta."""
    _cat()
    _prov("Cualquier Otro")
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("catalogo-nuevo")).content.decode()
    assert "🧮 Calculadora de costos" not in html
    assert "data-calc-proveedores" not in html


def test_alta_con_plymouth_guarda_insumos_y_alimenta_el_costo(client, usuario_factory):
    """El primer guardado ya NO tira los insumos (antes sólo `editar` los guardaba)."""
    from apps.el_catalogo.models import Servicio
    cat, prov = _cat(), _prov("Simil Cuero Plymouth")
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post(reverse("catalogo-nuevo"), {
        "nombre": "Portafolios nuevo", "descripcion_default": "",
        "costo": "0", "precio_base": "500", "categoria": str(cat.pk),
        "proveedores": str(prov.pk),
        "calc_material_0": "30", "calc_sublimacion_0": "10", "calc_mano_obra": "50",
    })
    assert r.status_code in (200, 302)
    srv = Servicio.objects.get(nombre="Portafolios nuevo")
    # Subtotal = (10 + 50) × 2.2 + 30 = 162 → alimenta el COSTO, no el precio.
    assert srv.costo == Decimal("162.00")
    assert srv.precio_base == Decimal("500.00")
    assert srv.detalles_costo.get("mano_obra") == "50"


def test_modal_de_alta_trae_la_calculadora(client, usuario_factory):
    _cat()
    _prov("Simil Cuero Plymouth")
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.get(reverse("catalogo-nuevo"), HTTP_HX_REQUEST="true")
    html = r.content.decode()
    assert "data-calc-box" in html
    # Y el ★ principal NO se pinta ahí (sería el bug 3b otra vez).
    assert 'name="proveedor_principal"' not in html


# ── Nota 4 · proveedor principal ───────────────────────────────────────────

def test_alta_deja_principal_el_primero_marcado(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    zeta, alfa = _prov("Zeta Bordados"), _prov("Alfa Textiles")
    client.force_login(usuario_factory(rol="super_admin"))
    r = client.post(reverse("catalogo-nuevo"), {
        "nombre": "Sin principal explícito", "descripcion_default": "",
        "costo": "0", "precio_base": "10", "categoria": str(cat.pk),
        "proveedores": [str(zeta.pk), str(alfa.pk)],
    })
    assert r.status_code in (200, 302)
    srv = Servicio.objects.get(nombre="Sin principal explícito")
    # El primero MARCADO, no el primero alfabético.
    assert srv.proveedor_principal_id == zeta.pk


def test_alta_respeta_el_principal_que_se_eligio(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    p1, p2 = _prov("Alfa Textiles"), _prov("Zeta Bordados")
    client.force_login(usuario_factory(rol="super_admin"))
    client.post(reverse("catalogo-nuevo"), {
        "nombre": "Con principal", "descripcion_default": "",
        "costo": "0", "precio_base": "10", "categoria": str(cat.pk),
        "proveedores": [str(p1.pk), str(p2.pk)],
        "proveedor_principal": str(p2.pk),
    })
    assert Servicio.objects.get(nombre="Con principal").proveedor_principal_id == p2.pk


def test_3a_la_tarjeta_pisa_el_proveedor_al_cambiar_de_producto():
    """Candado del contrato: el catálogo MANDA sobre el proveedor de la línea,
    igual que el costo desde agosto. Si vuelve el `!prov.value`, cambiar de
    producto deja pegado el proveedor del anterior."""
    js = (_raiz() / RUTA_JS_TARJETA).read_text()
    i = js.index('select[name$="-proveedor"]')
    tramo = js[i:i + 220]
    assert "datos.proveedor_id" in tramo
    assert "!prov.value" not in tramo
    # El costo conserva su contrato (mismo tipo de candado, desde agosto).
    assert "if (costo) costo.value = datos.costo;" in js
    # Y el PRECIO sigue sin pisarse: se negocia por proyecto.
    assert "if (precio && !precio.value) precio.value = datos.precio;" in js


def test_3b_el_dropdown_de_principal_se_sincroniza():
    """`pintar()` mantiene el ★ al día y `provAgregarOpcion` le suma la opción
    nueva (un proveedor creado inline no salía hasta recargar)."""
    html = (_raiz() / RUTA_FICHA).read_text()
    # La sincronía se dispara desde pintar(), que es lo que corre en cada cambio
    # y también lo que llama provAgregarOpcion.
    assert "sincronizarPrincipal(marcados);" in html
    assert "function sincronizarPrincipal" in html
    assert 'document.querySelector(\'[name="proveedor_principal"]\')' in html
    # provAgregarOpcion termina en pintar() → la opción nueva llega al ★.
    i = html.index("window.provAgregarOpcion")
    assert "pintar();" in html[i:i + 700]
    # Y hay aviso cuando el principal deja de surtir (antes era silencioso).
    assert 'id="prov-principal-aviso"' in html


# ── Nota 10 · archivar y eliminar en la ficha ──────────────────────────────

def test_ficha_muestra_archivar_y_eliminar(client, usuario_factory):
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    srv = Servicio.objects.create(nombre="Con acciones", precio_base=Decimal("1"), categoria=cat)
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("catalogo-editar", args=[srv.pk])).content.decode()
    assert reverse("catalogo-archivar", args=[srv.pk]) in html
    assert reverse("catalogo-eliminar", args=[srv.pk]) in html
    assert "Eliminar permanentemente" in html


def test_ficha_oculta_eliminar_sin_el_permiso(client, usuario_factory):
    """`catalogo.eliminar` sólo lo tiene el super admin (igual que en la lista)."""
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    srv = Servicio.objects.create(nombre="Sin eliminar", precio_base=Decimal("1"), categoria=cat)
    # Un usuario que puede editar y archivar pero NO eliminar (ese permiso sólo
    # lo trae el super admin por default).
    from cuentas.models.permiso_usuario import PermisoUsuario
    u = usuario_factory(rol="miembro")
    for accion in ("ver_nombres", "ver_precios", "editar", "archivar"):
        PermisoUsuario.objects.update_or_create(
            usuario=u, modulo="catalogo", permiso=accion, defaults={"activo": True})
    PermisoUsuario.objects.update_or_create(
        usuario=u, modulo="catalogo", permiso="eliminar", defaults={"activo": False})
    client.force_login(u)
    html = client.get(reverse("catalogo-editar", args=[srv.pk])).content.decode()
    assert reverse("catalogo-eliminar", args=[srv.pk]) not in html
    assert "Eliminar permanentemente" not in html
    # Archivar sí lo alcanza el contador.
    assert reverse("catalogo-archivar", args=[srv.pk]) in html


# ── Nota 11 · navegación entre categorías ──────────────────────────────────

def test_ficha_tiene_pastillas_de_categoria(client, usuario_factory):
    from apps.el_catalogo.models import CategoriaServicio, Servicio
    cat = _cat()
    otra = CategoriaServicio.objects.create(nombre="Otra familia", orden=2)
    srv = Servicio.objects.create(nombre="Navegable", precio_base=Decimal("1"), categoria=cat)
    client.force_login(usuario_factory(rol="super_admin"))
    html = client.get(reverse("catalogo-editar", args=[srv.pk])).content.decode()
    destino = f"{reverse('catalogo-lista')}?categoria={otra.pk}"
    assert destino in html
    assert "Otra familia" in html

def test_los_paneles_del_atajo_renderean_de_verdad(client, usuario_factory, proyecto_factory):
    """Los 4 paneles se pintan sin tronar y traen el selector.

    No es paranoia: el modal «Agregar producto» no lo renderizaba ninguna prueba,
    y una plantilla que nunca se pinta en pruebas se puede desplegar rota.
    """
    _cat()
    prov = _prov("Surtidor de prueba")
    admin = usuario_factory(rol="super_admin")
    proyecto = proyecto_factory(creado_por=admin)
    client.force_login(admin)
    paneles = [
        (reverse("proyectos-nuevo"), "qc"),
        (reverse("proyectos-detalle", args=[proyecto.pk]), "qc"),
        (reverse("proyectos-agregar-producto", args=[proyecto.pk]), "qcp"),
        (reverse("cotizaciones:nuevo"), "cot-qc"),
    ]
    for url, prefijo in paneles:
        r = client.get(url)
        assert r.status_code == 200, (url, r.status_code)
        html = r.content.decode()
        assert f'data-qc-prefijo="{prefijo}"' in html, url
        assert prov.razon_social in html, url

def test_la_tarjeta_clonada_recibe_el_proveedor_del_catalogo():
    """`construirTarjeta` NO dispara `change`, así que `prellenarServicio` no
    corre: el proveedor hay que ponerlo a mano o el producto que acabas de crear
    con su proveedor entra al proyecto sin él."""
    js = (_raiz() / RUTA_JS_TARJETA).read_text()
    i = js.index("initCard(card);")
    tramo = js[i:i + 700]
    assert "SERVICIOS_DATOS[servId]" in tramo
    assert 'select[name$="-proveedor"]' in tramo

def test_eliminar_de_la_ficha_no_vuelve_a_la_pagina_borrada(client, usuario_factory):
    """El `volver` del borrado NO puede apuntar a esta ficha: el producto deja de
    existir y volver ahí sería un 404. Archivar sí se queda (el producto sigue)."""
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    srv = Servicio.objects.create(nombre="A borrar", precio_base=Decimal("1"), categoria=cat)
    client.force_login(usuario_factory(rol="super_admin"))
    ficha = reverse("catalogo-editar", args=[srv.pk])
    lista = reverse("catalogo-lista")

    # Sin `?volver=`: el botón de borrar no manda destino → la vista cae a la lista.
    html = client.get(ficha).content.decode()
    i = html.index(reverse("catalogo-eliminar", args=[srv.pk]))
    assert "volver=" not in html[i:i + 160]

    # Con `?volver=` (llegaste de la lista filtrada): ése es el destino, no la ficha.
    html = client.get(f"{ficha}?volver={lista}%3Fq%3Dtest").content.decode()
    i = html.index(reverse("catalogo-eliminar", args=[srv.pk]))
    tramo = html[i:i + 200]
    assert "volver=" in tramo
    assert "editar" not in tramo.split("volver=")[1][:80]

def test_el_modal_de_borrado_lleva_el_volver_al_post(client, usuario_factory):
    """El destino tiene que sobrevivir el POST: el modal sólo lo recibía en el GET,
    así que borrar desde una lista filtrada perdía los filtros."""
    from apps.el_catalogo.models import Servicio
    cat = _cat()
    srv = Servicio.objects.create(nombre="Con destino", precio_base=Decimal("1"), categoria=cat)
    admin = usuario_factory(rol="super_admin")
    client.force_login(admin)
    destino = reverse("catalogo-lista") + "?q=algo"
    r = client.get(reverse("catalogo-eliminar", args=[srv.pk]), {"volver": destino},
                   HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert 'name="volver"' in r.content.decode()

    # Y el POST con ese destino redirige ahí, no a la lista pelona.
    r = client.post(reverse("catalogo-eliminar", args=[srv.pk]), {"volver": destino},
                    HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r.headers["HX-Redirect"] == destino
    assert not Servicio.objects.filter(pk=srv.pk).exists()
