"""De qué dirección sale un correo que manda El Chalán.

Oscar, 2026-08-23: «el correo salió de hola@ y no de chalán@. Repara eso.
Recuerda que esas cosas se tienen que configurar vía el GUI.»

Lo que cuidan estos tests: (a) que el hueco se cubra —una plantilla sin alias
propio ya no cae al remitente general cuando escribe El Chalán— y (b) que
cubrirlo NO le gane a lo más específico. Si el orden se invirtiera, una
cotización empezaría a salir de chalan@ en vez de la dirección de su plantilla,
y nadie lo notaría hasta que un cliente contestara al buzón equivocado.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.taller, pytest.mark.django_db]

CHALAN = "chalan@learningcenter.mx"
VENTAS = "ventas@learningcenter.mx"


@pytest.fixture
def alias(db):
    from ajustes.models import AliasRemitente

    def _crear(email, nombre="", usuario=None, verificado=True):
        obj, _ = AliasRemitente.objects.update_or_create(
            email=email,
            defaults={"nombre": nombre, "usuario": usuario, "verificado": verificado},
        )
        return obj

    return _crear


@pytest.fixture
def plantilla(db):
    from ajustes.models import PlantillaCorreo

    def _crear(remitente_email=""):
        return PlantillaCorreo.objects.create(
            slug="aviso", nombre="Aviso", asunto="Hola", cuerpo_html="<p>x</p>",
            activa=True, remitente_email=remitente_email,
        )

    return _crear


@pytest.fixture
def config_chalan(db):
    from ajustes.models import ConfiguracionCorreo

    def _fijar(email):
        cfg = ConfiguracionCorreo.obtener()
        cfg.remitente_chalan = email
        cfg.save(update_fields=["remitente_chalan"])
        return cfg

    return _fijar


# ── El hueco que Oscar reportó ───────────────────────────────────────────────

def test_plantilla_sin_alias_sale_del_remitente_del_chalan(alias, plantilla, config_chalan):
    """El caso exacto del reporte: salía de hola@ (el general) en vez de chalan@."""
    alias(CHALAN, "Chalán")
    config_chalan(CHALAN)
    from ajustes.models.alias_remitente import remitente_para

    assert CHALAN in remitente_para(plantilla(), usuario=None, origen="chalan")


def test_sin_origen_no_cambia_nada(alias, plantilla, config_chalan):
    """Las reglas automáticas y las campañas no pasan `origen`: siguen igual.

    Si esto se rompiera, el remitente de El Chalán se filtraría a TODO el correo
    del sistema sin que nadie lo hubiera pedido.
    """
    alias(CHALAN, "Chalán")
    config_chalan(CHALAN)
    from ajustes.models.alias_remitente import remitente_para

    assert remitente_para(plantilla(), usuario=None) == ""


# ── Lo específico gana ───────────────────────────────────────────────────────

def test_el_alias_de_la_plantilla_le_gana_al_del_chalan(alias, plantilla, config_chalan):
    """Una cotización sale de la dirección de su plantilla, la mande quien la mande."""
    alias(CHALAN, "Chalán")
    alias(VENTAS, "VENTAS")
    config_chalan(CHALAN)
    from ajustes.models.alias_remitente import remitente_para

    salida = remitente_para(plantilla(remitente_email=VENTAS), usuario=None, origen="chalan")
    assert VENTAS in salida
    assert CHALAN not in salida


def test_lo_elegido_a_mano_le_gana_a_todo(alias, plantilla, config_chalan):
    alias(CHALAN, "Chalán")
    alias(VENTAS, "VENTAS")
    config_chalan(CHALAN)
    from ajustes.models.alias_remitente import remitente_para

    salida = remitente_para(plantilla(), usuario=None, forzado=VENTAS, origen="chalan")
    assert VENTAS in salida


# ── Casos de borde: sin configurar, y un alias que ya no existe ──────────────

def test_sin_configurar_cae_al_remitente_general(plantilla):
    """Vacío es una respuesta válida: El Cartero pone el remitente de siempre."""
    from ajustes.models.alias_remitente import remitente_para

    assert remitente_para(plantilla(), usuario=None, origen="chalan") == ""


def test_alias_configurado_pero_borrado_del_registro_se_respeta(plantilla, config_chalan):
    """Quien lo escribió sabía lo que hacía; se manda sin nombre visible."""
    config_chalan("otra@learningcenter.mx")
    from ajustes.models.alias_remitente import remitente_para

    assert remitente_para(plantilla(), usuario=None, origen="chalan") == "otra@learningcenter.mx"


def test_un_alias_personal_ajeno_no_se_usa_ni_por_el_chalan(alias, plantilla, config_chalan, django_user_model):
    """La regla de S-Alias-Personales sigue mandando: nadie firma por otro."""
    duenio = django_user_model.objects.create_user(
        email="alex@ejemplo.mx", password="x", nombre_completo="Alex",
    )
    alias("alex@learningcenter.mx", "Alexandro", usuario=duenio)
    config_chalan("alex@learningcenter.mx")
    from ajustes.models.alias_remitente import remitente_para

    assert remitente_para(plantilla(), usuario=None, origen="chalan") == ""
