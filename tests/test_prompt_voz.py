"""Voz editable de Los Chalanes (Prompt base + voces por estación).

Cubre el modelo PromptVoz, el helper `voz()`/`preludio()`, el saneo del
contenido y la invalidación de caché por signal.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_limpio():
    from chalanes.voz import invalidar_cache_voz
    invalidar_cache_voz()
    yield
    invalidar_cache_voz()


def test_slots_seedeados():
    from chalanes.models import PromptVoz
    claves = set(PromptVoz.objects.values_list("clave", flat=True))
    assert {"base", "dictado", "taller_chat", "ocr_recibo", "kpi_dsl"} <= claves


def test_voz_vacia_devuelve_cadena_vacia():
    from chalanes.voz import voz
    assert voz("base") == ""
    assert voz("dictado") == ""


def test_voz_con_contenido():
    from chalanes.models import PromptVoz
    from chalanes.voz import voz
    pv = PromptVoz.objects.get(clave="base")
    pv.contenido = "Sé formal y conciso."
    pv.save()
    assert voz("base") == "Sé formal y conciso."


def test_voz_sanea_payload():
    from chalanes.models import PromptVoz
    from chalanes.voz import voz
    pv = PromptVoz.objects.get(clave="dictado")
    pv.contenido = "Hola <script>alert(1)</script> mundo"
    pv.save()
    out = voz("dictado")
    assert "<script>" not in out
    assert "Hola" in out


def test_preludio_combina_base_y_estacion():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, preludio
    PromptVoz.objects.filter(clave="base").update(contenido="VOZBASE")
    PromptVoz.objects.filter(clave="dictado").update(contenido="VOZDICTADO")
    invalidar_cache_voz()  # update() no dispara signal
    pre = preludio("dictado")
    assert "VOZBASE" in pre
    assert "VOZDICTADO" in pre
    assert pre.endswith("\n\n")


def test_preludio_vacio_si_no_hay_voz():
    from chalanes.voz import preludio
    assert preludio("dictado") == ""


def test_preludio_solo_base():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, preludio
    PromptVoz.objects.filter(clave="base").update(contenido="SOLOBASE")
    invalidar_cache_voz()
    pre = preludio("kpi_dsl")
    assert "SOLOBASE" in pre


def test_signal_invalida_cache():
    from chalanes.models import PromptVoz
    from chalanes.voz import voz
    assert voz("base") == ""  # cachea el mapa vacío
    pv = PromptVoz.objects.get(clave="base")
    pv.contenido = "NUEVO"
    pv.save()  # el signal limpia el caché
    assert voz("base") == "NUEVO"


# ── Capa aditiva: voz personal del usuario (S-Chalan-Voz-Usuario) ──────


class _UsuarioFalso:
    """Duck-type para `_voz_personal` — solo necesita el atributo."""

    def __init__(self, voz_chalan=""):
        self.voz_chalan = voz_chalan


def test_preludio_agrega_voz_personal_del_usuario():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, preludio
    PromptVoz.objects.filter(clave="base").update(contenido="VOZBASE")
    invalidar_cache_voz()
    u = _UsuarioFalso(voz_chalan="Háblame de tú.")
    pre = preludio("dictado", u)
    assert "VOZBASE" in pre
    assert "Háblame de tú." in pre


def test_preludio_sin_usuario_no_lleva_voz_personal():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, preludio
    PromptVoz.objects.filter(clave="base").update(contenido="VOZBASE")
    invalidar_cache_voz()
    pre = preludio("dictado")  # usuario=None
    assert "VOZBASE" in pre


def test_voz_personal_vacia_no_inyecta_nada():
    from chalanes.voz import preludio
    u = _UsuarioFalso(voz_chalan="")
    # Sin voz global ni personal → preludio vacío.
    assert preludio("dictado", u) == ""


def test_voz_personal_se_sanea():
    from chalanes.voz import preludio
    u = _UsuarioFalso(voz_chalan="Hola <script>alert(1)</script> directo")
    pre = preludio("taller_chat", u)
    assert "<script>" not in pre
    assert "directo" in pre


# ── Reglas operativas (slot estructural global) ───────────────────────


def test_reglas_slot_seedeado():
    from chalanes.models import PromptVoz
    assert PromptVoz.objects.filter(clave="reglas_operativas").exists()


def test_reglas_vacio_devuelve_cadena_vacia():
    from chalanes.voz import reglas
    assert reglas() == ""


def test_reglas_con_contenido_envuelve_en_bloque():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, reglas
    PromptVoz.objects.filter(clave="reglas_operativas").update(
        contenido="Si el cliente es urgente, sube prioridad a 8.")
    invalidar_cache_voz()
    out = reglas()
    assert "REGLAS OPERATIVAS" in out
    assert "prioridad a 8" in out


def test_reglas_se_sanea():
    from chalanes.models import PromptVoz
    from chalanes.voz import invalidar_cache_voz, reglas
    PromptVoz.objects.filter(clave="reglas_operativas").update(
        contenido="regla <script>x</script> segura")
    invalidar_cache_voz()
    out = reglas()
    assert "<script>" not in out
    assert "segura" in out
