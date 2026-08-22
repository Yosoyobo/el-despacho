"""El Chalán con las plantillas: manda cualquiera, y las que redacta nacen apagadas."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def accion_factory(db, usuario_factory):
    """Una DictadoAccion suelta, que es lo que recibe un ejecutor."""
    from apps.el_dictado.models import Dictado, DictadoAccion

    def _crear(tipo, payload, usuario=None):
        usuario = usuario or usuario_factory(rol="super_admin")
        dictado = Dictado.objects.create(
            texto_crudo="prueba", autor=usuario, estado="interpretado",
        )
        return DictadoAccion.objects.create(
            dictado=dictado, tipo=tipo, descripcion="prueba",
            payload=payload, orden=0, confianza=1.0,
        )

    return _crear


@pytest.fixture
def cartero_espia(monkeypatch):
    enviados: list[dict] = []

    def _fake(*, destinatario, asunto, html, texto="", adjuntos=None, remitente=""):
        from lib.cartero import ResultadoCorreo
        enviados.append({"destinatario": destinatario, "asunto": asunto,
                         "html": html, "remitente": remitente})
        return ResultadoCorreo(ok=True, proveedor="smtp")

    monkeypatch.setattr("lib.cartero.enviar", _fake)
    return enviados


# ── Crear plantillas ─────────────────────────────────────────────────────────


def test_la_plantilla_que_redacta_nace_apagada(accion_factory, usuario_factory):
    """La salvaguarda del sprint: una plantilla acaba en la bandeja de un
    cliente, así que no puede quedar lista para enviarse sin que alguien la
    lea."""
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("crear_plantilla_correo", {
        "nombre": "Aviso de entrega",
        "asunto": "Tu pedido está listo",
        "cuerpo_html": "<p>Hola {{ cliente }}</p>",
    }, usuario=u)
    EJECUTORES["crear_plantilla_correo"](accion, u)

    from ajustes.models import PlantillaCorreo
    pl = PlantillaCorreo.objects.get(slug="aviso-de-entrega")
    assert pl.activa is False
    assert pl.origen == "chalan"
    assert pl.es_borrador is True
    assert pl not in PlantillaCorreo.enviables()


def test_dos_plantillas_con_el_mismo_nombre_no_chocan(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    for _ in range(2):
        accion = accion_factory("crear_plantilla_correo", {"nombre": "Aviso"}, usuario=u)
        EJECUTORES["crear_plantilla_correo"](accion, u)
    assert PlantillaCorreo.objects.filter(nombre="Aviso").count() == 2


def test_sin_nombre_no_crea_nada(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("crear_plantilla_correo", {"asunto": "x"}, usuario=u)
    with pytest.raises(ValueError, match="nombre"):
        EJECUTORES["crear_plantilla_correo"](accion, u)


def test_un_alias_invalido_se_rechaza(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("crear_plantilla_correo", {
        "nombre": "Aviso", "remitente_email": "esto-no-es-correo",
    }, usuario=u)
    with pytest.raises(ValueError, match="correo válido"):
        EJECUTORES["crear_plantilla_correo"](accion, u)


def test_sin_permiso_no_puede_crear_plantillas(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="disenador")
    accion = accion_factory("crear_plantilla_correo", {"nombre": "Aviso"}, usuario=u)
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["crear_plantilla_correo"](accion, u)


# ── Enviar ───────────────────────────────────────────────────────────────────


def test_manda_una_plantilla_propia_por_su_slug(
    accion_factory, usuario_factory, cliente_factory, cartero_espia,
):
    from apps.el_dictado.ejecutores import EJECUTORES

    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    cliente = cliente_factory(razon_social="Kari Kari", email_contacto="kari@ejemplo.com")
    PlantillaCorreo.objects.create(
        slug="aviso-entrega", nombre="Aviso", asunto="Listo, {{ cliente }}",
        cuerpo_html="<p>Ya está</p>", activa=True,
        remitente_email="cobranza@learningcenter.mx", remitente_nombre="Cobranza",
    )
    accion = accion_factory("enviar_correo", {
        "cliente_slug": cliente.slug, "tipo_plantilla": "aviso-entrega",
    }, usuario=u)
    EJECUTORES["enviar_correo"](accion, u)

    assert cartero_espia[0]["destinatario"] == "kari@ejemplo.com"
    assert cartero_espia[0]["remitente"] == "Cobranza <cobranza@learningcenter.mx>"


def test_puede_mandar_a_una_direccion_dictada(
    accion_factory, usuario_factory, cartero_espia,
):
    """Decisión de Oscar: se permite dictar la dirección. El preview la muestra
    antes de que salga."""
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("enviar_correo", {
        "email": "quien.sea@ejemplo.com", "tipo_plantilla": "generico",
        "mensaje": "Buenas tardes",
    }, usuario=u)
    EJECUTORES["enviar_correo"](accion, u)
    assert cartero_espia[0]["destinatario"] == "quien.sea@ejemplo.com"


def test_una_direccion_con_dedazo_se_rechaza(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("enviar_correo", {
        "email": "correo-sin-arroba", "tipo_plantilla": "generico", "mensaje": "hola",
    }, usuario=u)
    with pytest.raises(ValueError, match="no parece un correo"):
        EJECUTORES["enviar_correo"](accion, u)


def test_sin_destinatario_pide_uno(accion_factory, usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="super_admin")
    accion = accion_factory("enviar_correo", {
        "tipo_plantilla": "generico", "mensaje": "hola",
    }, usuario=u)
    with pytest.raises(ValueError, match="a quién"):
        EJECUTORES["enviar_correo"](accion, u)


def test_una_plantilla_apagada_no_se_manda(
    accion_factory, usuario_factory, cliente_factory,
):
    """Cierra el círculo: el borrador del Chalán no se puede enviar ni
    pidiéndoselo por su slug."""
    from apps.el_dictado.ejecutores import EJECUTORES

    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    PlantillaCorreo.objects.create(
        slug="borrador-x", nombre="Borrador", activa=False, origen="chalan",
    )
    accion = accion_factory("enviar_correo", {
        "cliente_slug": cliente.slug, "tipo_plantilla": "borrador-x",
    }, usuario=u)
    with pytest.raises(ValueError, match="plantilla activa"):
        EJECUTORES["enviar_correo"](accion, u)


def test_sin_permiso_no_manda_correos(accion_factory, usuario_factory, cliente_factory):
    from apps.el_dictado.ejecutores import EJECUTORES

    u = usuario_factory(rol="disenador")
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    accion = accion_factory("enviar_correo", {
        "cliente_slug": cliente.slug, "tipo_plantilla": "generico", "mensaje": "hola",
    }, usuario=u)
    with pytest.raises(ValueError, match="permiso"):
        EJECUTORES["enviar_correo"](accion, u)


# ── MCP ──────────────────────────────────────────────────────────────────────


def test_la_capacidad_mcp_lista_las_plantillas(usuario_factory):
    import capacidades
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    PlantillaCorreo.objects.create(slug="aviso", nombre="Aviso", activa=True)
    PlantillaCorreo.objects.create(
        slug="pendiente", nombre="Pendiente", activa=False, origen="chalan",
    )
    salida = capacidades.ejecutar("listar_plantillas_correo", {}, u)
    # Sobre los DATOS, no sobre el texto: la salida se recorta para el LLM, así
    # que buscar una cadena en ella depende de cuántas plantillas haya.
    slugs = {p["slug"] for p in salida["plantillas"]}
    assert "aviso" in slugs
    assert "pendiente" not in slugs  # apagada: no se puede mandar
    assert salida["borradores_sin_revisar"] == 1


def test_los_tres_lugares_del_contrato_estan_sincronizados():
    """Si un ejecutor no está en el catálogo, el prompt nunca lo enumera y el
    Chalán no sabe que existe."""
    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO

    tipos_catalogo = {c["tipo"] for c in COMANDOS_DICTADO}
    for tipo in ("crear_plantilla_correo", "enviar_correo"):
        assert tipo in EJECUTORES, f"{tipo} sin ejecutor"
        assert tipo in tipos_catalogo, f"{tipo} fuera del catálogo"


def test_las_propias_van_antes_que_las_de_sistema(usuario_factory):
    """El registro poda las listas antes de enseñárselas al LLM. Con las 6 de
    sistema al frente, las plantillas del usuario caían fuera del corte y El
    Chalán no sabía que existían."""
    import capacidades
    from ajustes.models import PlantillaCorreo

    u = usuario_factory(rol="super_admin")
    for slug in ("cotizacion", "factura", "cobranza", "pago", "bienvenida"):
        PlantillaCorreo.obtener(slug)
    PlantillaCorreo.objects.create(slug="zzz-mia", nombre="Zzz mía", activa=True)

    salida = capacidades.ejecutar("listar_plantillas_correo", {}, u)
    assert salida["plantillas"][0]["slug"] == "zzz-mia"


def test_una_plantilla_de_sistema_se_puede_mandar_aunque_no_tenga_fila(
    accion_factory, usuario_factory, cliente_factory, cartero_espia,
):
    """Las de sistema siempre tienen que poder mandarse: si nadie ha abierto
    nunca «bienvenida», la fila puede no existir todavía y aun así hay que
    poder usarla."""
    from ajustes.models import PlantillaCorreo
    from apps.el_dictado.ejecutores import EJECUTORES

    PlantillaCorreo.objects.filter(slug="bienvenida").delete()
    u = usuario_factory(rol="super_admin")
    cliente = cliente_factory(email_contacto="c@ejemplo.com")
    accion = accion_factory("enviar_correo", {
        "cliente_slug": cliente.slug, "tipo_plantilla": "bienvenida",
    }, usuario=u)
    EJECUTORES["enviar_correo"](accion, u)
    assert cartero_espia[0]["destinatario"] == "c@ejemplo.com"
