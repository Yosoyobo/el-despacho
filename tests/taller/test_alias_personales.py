"""La regla de Oscar: un alias personal sale a nombre de su dueño y de nadie más.

Lo que cuidan estos tests, y por qué importa: si la regla se rompe, un correo
sale FIRMADO POR OTRA PERSONA. No hay error, no hay rebote — el cliente
simplemente recibe algo que parece mandado por alguien que nunca lo mandó.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]


@pytest.fixture
def alias_factory(db):
    from ajustes.models import AliasRemitente

    def _crear(email, nombre="", usuario=None, verificado=True):
        # update_or_create y no create: los alias reales de Learning Center ya
        # vienen sembrados por la migración, así que en la vida real lo que se
        # hace con ellos es asignarles dueño, no crearlos.
        alias, _ = AliasRemitente.objects.update_or_create(
            email=email,
            defaults={"nombre": nombre, "usuario": usuario, "verificado": verificado},
        )
        return alias

    return _crear


@pytest.fixture
def plantilla_con(db):
    from ajustes.models import PlantillaCorreo

    def _crear(remitente_email="", nombre_remitente=""):
        return PlantillaCorreo.objects.create(
            slug="aviso", nombre="Aviso", asunto="Hola", cuerpo_html="<p>x</p>",
            activa=True, remitente_email=remitente_email,
            remitente_nombre=nombre_remitente,
        )

    return _crear


# ── Quién puede usar qué ─────────────────────────────────────────────────────


def test_un_departamental_lo_usa_cualquiera(alias_factory, usuario_factory):
    alias = alias_factory("cobranza@learningcenter.mx", "COBRANZA")
    assert alias.puede_usarlo(usuario_factory()) is True
    assert alias.puede_usarlo(usuario_factory(rol="super_admin")) is True


def test_un_personal_solo_lo_usa_su_dueno(alias_factory, usuario_factory):
    jorge = usuario_factory(email="jorge@ejemplo.com")
    otro = usuario_factory(email="alex@ejemplo.com")
    alias = alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    assert alias.puede_usarlo(jorge) is True
    assert alias.puede_usarlo(otro) is False


def test_un_personal_sin_dueno_no_lo_usa_nadie(alias_factory, usuario_factory):
    """Lado seguro: recién sembrado, alex@ y jorge@ no tienen dueño asignado."""
    alias = alias_factory("jorge@learningcenter.mx", "Jorge")
    alias.usuario = None
    alias.save()
    # Sin dueño no es personal, así que es del despacho — es el otro lado de la
    # moneda y hay que tenerlo claro: `es_personal` depende del FK.
    assert alias.es_personal is False


def test_ningun_personal_aplica_sin_usuario_detras(alias_factory, usuario_factory):
    """Un cron o una regla automática no puede firmar por una persona."""
    jorge = usuario_factory()
    alias = alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    assert alias.puede_usarlo(None) is False


# ── La decisión del remitente (fuente única) ─────────────────────────────────


def test_la_plantilla_con_alias_propio_sale_a_su_nombre(
    alias_factory, plantilla_con, usuario_factory,
):
    from ajustes.models.alias_remitente import remitente_para

    jorge = usuario_factory()
    alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    pl = plantilla_con("jorge@learningcenter.mx", "Jorge")
    assert remitente_para(pl, jorge) == "Jorge <jorge@learningcenter.mx>"


def test_el_alias_personal_ajeno_cae_al_general_sin_fallar(
    alias_factory, plantilla_con, usuario_factory,
):
    """Decisión de Oscar: la plantilla la puede seguir mandando cualquiera, sólo
    que no a nombre de su dueño."""
    from ajustes.models.alias_remitente import remitente_para

    jorge = usuario_factory()
    alex = usuario_factory()
    alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    pl = plantilla_con("jorge@learningcenter.mx", "Jorge")
    assert remitente_para(pl, alex) == ""


def test_un_departamental_en_la_plantilla_lo_usa_cualquiera(
    alias_factory, plantilla_con, usuario_factory,
):
    from ajustes.models.alias_remitente import remitente_para

    alias_factory("cobranza@learningcenter.mx", "COBRANZA")
    pl = plantilla_con("cobranza@learningcenter.mx", "COBRANZA | LEARNING CENTER")
    esperado = "COBRANZA | LEARNING CENTER <cobranza@learningcenter.mx>"
    assert remitente_para(pl, usuario_factory()) == esperado


def test_elegir_a_mano_pisa_al_de_la_plantilla(
    alias_factory, plantilla_con, usuario_factory,
):
    from ajustes.models.alias_remitente import remitente_para

    alias_factory("ventas@learningcenter.mx", "VENTAS")
    pl = plantilla_con("cobranza@learningcenter.mx", "COBRANZA")
    salida = remitente_para(pl, usuario_factory(), forzado="ventas@learningcenter.mx")
    assert salida == "VENTAS <ventas@learningcenter.mx>"


def test_no_se_puede_elegir_el_alias_de_otro(
    alias_factory, plantilla_con, usuario_factory,
):
    """El `<select>` se puede manipular: la validación está en el servidor."""
    from ajustes.models.alias_remitente import remitente_para

    jorge = usuario_factory()
    alex = usuario_factory()
    alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    pl = plantilla_con()
    assert remitente_para(pl, alex, forzado="jorge@learningcenter.mx") == ""


def test_una_direccion_inventada_no_se_respeta(plantilla_con, usuario_factory):
    from ajustes.models.alias_remitente import remitente_para

    pl = plantilla_con()
    assert remitente_para(pl, usuario_factory(), forzado="quien@sea.com") == ""


# ── Qué se ofrece a cada quien ───────────────────────────────────────────────


def test_a_cada_quien_se_le_ofrece_lo_suyo(alias_factory, usuario_factory):
    from ajustes.models.alias_remitente import disponibles_para

    jorge = usuario_factory()
    alex = usuario_factory()
    alias_factory("cobranza@learningcenter.mx", "COBRANZA")
    alias_factory("jorge@learningcenter.mx", "Jorge", usuario=jorge)
    alias_factory("alex@learningcenter.mx", "Alexandro", usuario=alex)

    de_jorge = {a.email for a in disponibles_para(jorge)}
    assert "cobranza@learningcenter.mx" in de_jorge
    assert "jorge@learningcenter.mx" in de_jorge
    assert "alex@learningcenter.mx" not in de_jorge


def test_una_direccion_sin_comprobar_no_se_ofrece(alias_factory, usuario_factory):
    """Ofrecer una que Google va a reescribir sería prometer algo que no pasa."""
    from ajustes.models.alias_remitente import disponibles_para

    alias_factory("nueva@learningcenter.mx", "NUEVA", verificado=False)
    emails = {a.email for a in disponibles_para(usuario_factory())}
    assert "nueva@learningcenter.mx" not in emails


# ── Los alias reales de Learning Center ──────────────────────────────────────


def test_los_alias_de_learning_center_vienen_sembrados():
    from ajustes.models import AliasRemitente

    esperados = {
        "hola@learningcenter.mx", "admin@learningcenter.mx",
        "cobranza@learningcenter.mx", "facturas@learningcenter.mx",
        "legal@learningcenter.mx", "pagos@learningcenter.mx",
        "runner@learningcenter.mx", "soporte@learningcenter.mx",
        "ventas@learningcenter.mx", "chalan@learningcenter.mx",
        "alex@learningcenter.mx", "jorge@learningcenter.mx",
    }
    hay = set(AliasRemitente.objects.values_list("email", flat=True))
    assert esperados <= hay


def test_los_sembrados_ya_estan_comprobados():
    """Los dio de alta Oscar en Google: nadie tiene que volver a comprobarlos."""
    from ajustes.models import AliasRemitente

    assert AliasRemitente.objects.get(email="cobranza@learningcenter.mx").verificado


def test_ninguna_direccion_sembrada_sale_como_pendiente():
    from ajustes.models.alias_remitente import faltan_por_dar_de_alta

    assert faltan_por_dar_de_alta() == []
