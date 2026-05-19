"""S2b.2 — El Dictado: interpretación + ejecutores + aplicación atómica."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def _mock_resultado(texto_json: str, *, provider: str = "anthropic", modelo: str = "claude-opus-4-7"):
    """Construye un `Resultado` falso del Chalán que devuelve `texto_json`."""
    from lib.analistas.base import Resultado
    return Resultado(
        texto=texto_json, provider=provider, modelo=modelo,
        prompt_tokens=100, completion_tokens=200, costo_usd=0.001, latencia_ms=50,
    )


def _seed_cuadro():
    """Estación dictado debe existir para que cadena_de() resuelva."""
    from ajustes.models.credencial import Credencial
    from chalanes.models import CuadroChalanes
    Credencial.guardar("chalan_anthropic_api_key", "sk-ant-test")
    CuadroChalanes.objects.update_or_create(
        estacion="dictado",
        defaults={"proveedor": "anthropic", "modelo": "claude-opus-4-7"},
    )


# ── Interpretación ──


def test_interpretar_acciones_validas_persiste_dictado(usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    from apps.el_dictado.models import Dictado
    from apps.el_dictado.services import interpretar

    fake_json = json.dumps({
        "pregunta_clarificacion": None,
        "acciones": [
            {"tipo": "crear_recado", "descripcion": "Avisar a Maria",
             "payload": {"destinatarios_slugs": ["maria"], "cuerpo": "Hola"}, "confianza": 0.95},
        ],
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(fake_json)
        dictado = interpretar(texto="avísale a @maria", usuario=u)

    assert dictado.estado == "esperando_confirmacion"
    assert dictado.acciones.count() == 1
    assert dictado.acciones.first().tipo == "crear_recado"
    assert Dictado.objects.filter(autor=u).count() == 1


def test_interpretar_pregunta_clarificacion(usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    from apps.el_dictado.services import interpretar

    fake_json = json.dumps({
        "pregunta_clarificacion": "¿A cuál heladería te refieres?",
        "acciones": [],
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(fake_json)
        dictado = interpretar(texto="cobra a la heladería", usuario=u)

    assert dictado.estado == "preguntando"
    assert "heladería" in dictado.pregunta_clarificacion


def test_interpretar_fallo_total_devuelve_fallo_ia(usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    from apps.el_dictado.services import interpretar

    from lib.analistas.reemplazo import TodosFallaron

    with patch("lib.analistas.analizar") as mock:
        mock.side_effect = TodosFallaron([("anthropic", "timeout")])
        dictado = interpretar(texto="texto cualquiera", usuario=u)

    assert dictado.estado == "fallo_ia"
    assert "error" in dictado.interpretacion_raw


def test_interpretar_json_invalido_devuelve_fallo_ia(usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    from apps.el_dictado.services import interpretar

    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado("no es json {{{")
        dictado = interpretar(texto="x", usuario=u)
    assert dictado.estado == "fallo_ia"


def test_interpretar_filtra_tipo_prohibido(usuario_factory):
    _seed_cuadro()
    u = usuario_factory(rol="dueno")
    from apps.el_dictado.services import interpretar

    fake_json = json.dumps({
        "pregunta_clarificacion": None,
        "acciones": [
            {"tipo": "crear_recado", "descripcion": "ok",
             "payload": {"destinatarios_slugs": ["x"], "cuerpo": "y"}, "confianza": 0.9},
            {"tipo": "modificar_ajustes", "descripcion": "prohibida",
             "payload": {}, "confianza": 0.9},
        ],
    })
    with patch("lib.analistas.analizar") as mock:
        mock.return_value = _mock_resultado(fake_json)
        dictado = interpretar(texto="x", usuario=u)

    tipos = {a.tipo for a in dictado.acciones.all()}
    assert "modificar_ajustes" not in tipos


# ── Ejecutores ──


def test_ejecutor_crear_tarea_funciona(usuario_factory, proyecto_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_pizarron.models import Tarea

    actor = usuario_factory(rol="dueno")
    asignada = usuario_factory(rol="disenador", email="maria@a.com")
    p = proyecto_factory()
    p.refresh_from_db()  # asegurar slug

    d = Dictado.objects.create(autor=actor, texto_crudo="x", estado="esperando_confirmacion")
    a = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="crear_tarea", descripcion="Crea tarea",
        payload={"proyecto_slug": p.slug, "titulo": "Mandar contrato", "asignado_slug": asignada.slug},
    )
    EJECUTORES["crear_tarea"](a, actor)
    assert Tarea.objects.filter(proyecto=p, titulo="Mandar contrato", asignada_a=asignada).exists()
    assert a.entidad_tipo == "tarea"


def test_ejecutor_crear_recado_funciona(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.recados.models import Recado

    autor = usuario_factory(rol="dueno")
    maria = usuario_factory(rol="disenador", email="maria@a.com")
    d = Dictado.objects.create(autor=autor, texto_crudo="x", estado="esperando_confirmacion")
    a = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="crear_recado", descripcion="Recado",
        payload={"destinatarios_slugs": [maria.slug], "cuerpo": "Hola María"},
    )
    EJECUTORES["crear_recado"](a, autor)
    assert Recado.objects.filter(autor=autor, cuerpo="Hola María").exists()


def test_ejecutor_registrar_egreso_es_stub(usuario_factory):
    from apps.el_dictado.ejecutores import EJECUTORES
    from apps.el_dictado.models import Dictado, DictadoAccion

    u = usuario_factory(rol="dueno")
    d = Dictado.objects.create(autor=u, texto_crudo="x", estado="esperando_confirmacion")
    a = DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="registrar_egreso", descripcion="Egreso",
        payload={"monto": 100},
    )
    with pytest.raises(ValueError, match="S2b.3"):
        EJECUTORES["registrar_egreso"](a, u)


def test_aplicacion_atomica_por_accion(usuario_factory, proyecto_factory, monkeypatch):
    """Una acción que falla NO aborta las demás."""
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import aplicar

    u = usuario_factory(rol="dueno")
    p = proyecto_factory()
    p.refresh_from_db()
    d = Dictado.objects.create(autor=u, texto_crudo="x", estado="esperando_confirmacion")
    # 2 acciones: una ejecutable + una que rompe
    DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="actualizar_proyecto", descripcion="ok",
        payload={"proyecto_slug": p.slug, "campos": {"descripcion": "nuevo"}},
    )
    DictadoAccion.objects.create(
        dictado=d, orden=1, tipo="actualizar_proyecto", descripcion="rota",
        payload={"proyecto_slug": "no-existe", "campos": {"descripcion": "x"}},
    )
    resultado = aplicar(dictado=d, usuario=u)
    assert resultado["aplicadas"] == 1
    assert resultado["fallidas"] == 1
    d.refresh_from_db()
    assert d.estado == "aplicado_con_errores"


def test_aplicacion_solo_acciones_confirmadas(usuario_factory, proyecto_factory):
    from apps.el_dictado.models import Dictado, DictadoAccion
    from apps.el_dictado.services import aplicar

    u = usuario_factory(rol="dueno")
    p = proyecto_factory()
    p.refresh_from_db()
    d = Dictado.objects.create(autor=u, texto_crudo="x", estado="esperando_confirmacion")
    DictadoAccion.objects.create(
        dictado=d, orden=0, tipo="actualizar_proyecto", descripcion="ok",
        payload={"proyecto_slug": p.slug, "campos": {"descripcion": "X"}},
        confirmada=False,  # ← desmarcada
    )
    aplicar(dictado=d, usuario=u)
    p.refresh_from_db()
    assert p.descripcion != "X"  # no se aplicó


# ── Histórico ──


def test_historial_solo_propios(client, usuario_factory):
    from apps.el_dictado.models import Dictado

    u1 = usuario_factory(rol="dueno", email="a@a.com")
    u2 = usuario_factory(rol="dueno", email="b@a.com")
    Dictado.objects.create(autor=u1, texto_crudo="mío", estado="aplicado")
    Dictado.objects.create(autor=u2, texto_crudo="ajeno", estado="aplicado")

    client.force_login(u1)
    resp = client.get("/dictado/historial/")
    assert resp.status_code == 200
    assert b"m\xc3\xado" in resp.content  # "mío" UTF-8
    assert b"ajeno" not in resp.content


def test_detalle_404_si_no_es_autor(client, usuario_factory):
    from apps.el_dictado.models import Dictado

    u1 = usuario_factory(rol="dueno", email="a@a.com")
    u2 = usuario_factory(rol="dueno", email="b@a.com")
    d = Dictado.objects.create(autor=u1, texto_crudo="x", estado="aplicado")

    client.force_login(u2)
    resp = client.get(f"/dictado/{d.pk}/")
    assert resp.status_code == 404


# ── UI ──


def test_home_muestra_textbox_activo(client, usuario_factory):
    u = usuario_factory(rol="dueno")
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # El textbox ya no está disabled
    assert 'name="texto"' in body
    assert "/dictado/interpretar" in body
    assert "esta función llega en sprint" not in body  # ya no es placeholder


def test_aprendizajes_se_inyectan_en_prompt(usuario_factory):
    """Aprendizajes activos con peso_efectivo >= 0.3 entran en el prompt."""
    from apps.el_dictado.models import DictadoAprendizaje
    from apps.el_dictado.prompt import aprendizajes_activos

    u = usuario_factory(rol="dueno")
    DictadoAprendizaje.objects.create(
        autor=u, frase_o_patron="la heladería",
        interpretacion_correcta="$heladeria-michoacana", peso=1.0,
    )
    DictadoAprendizaje.objects.create(
        autor=u, frase_o_patron="apagado", interpretacion_correcta="x", peso=0.1, activo=False,
    )
    activos = aprendizajes_activos()
    frases = {a["frase"] for a in activos}
    assert "la heladería" in frases
    assert "apagado" not in frases
