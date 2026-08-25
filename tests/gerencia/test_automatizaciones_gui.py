"""La pantalla de automatizaciones (n8n) en La Gerencia.

Oscar, 2026-08-24: «quiero un menú GUI de n8n, ¿qué hace? No sé, recomienda».
Lo que se cuida, en orden de lo que dolería:

1. **Que prender no se dé por hecho.** n8n puede negarse (a un flujo le falta
   una credencial) y responder que sí sin haber cambiado nada. Decir «listo»
   sin comprobarlo deja a alguien creyendo que ya corre.
2. **Que una automatización recién creada nazca APAGADA.** Un flujo que arranca
   solo puede escribirle a un cliente antes de que nadie lo haya visto
   funcionar.
3. **Que «no contesta» y «no hay ninguna» se distingan.** Son dos problemas
   distintos y mandan a buscar en lugares distintos.
4. Que sin llave la pantalla explique dónde se saca, en vez de verse rota.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def jefe(client, usuario_factory):
    u = usuario_factory(rol="super_admin")
    client.force_login(u)
    return u


# ── La puerta ──────────────────────────────────────────────────────────────


def test_sin_permiso_no_se_entra(client, usuario_factory):
    client.force_login(usuario_factory(rol="miembro"))
    assert client.get("/ajustes/automatizaciones/").status_code in (302, 403)


def test_sin_llave_dice_donde_sacarla(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: False)
    r = client.get("/ajustes/automatizaciones/")
    cuerpo = r.content.decode()
    assert r.status_code == 200
    assert "Falta la llave" in cuerpo
    assert "Configuración → API" in cuerpo


def test_con_llave_pero_sin_respuesta_no_dice_que_no_hay_ninguna(
        client, jefe, monkeypatch):  # noqa: ARG001
    """«No contesta» y «no hay ninguna» mandan a buscar el problema a lugares
    distintos. Confundirlas cuesta media hora."""
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: None)
    monkeypatch.setattr(n8n, "ejecuciones", lambda **k: None)

    cuerpo = client.get("/ajustes/automatizaciones/").content.decode()
    assert "no contesta" in cuerpo
    assert "Todavía no hay ninguna" not in cuerpo


def test_sin_flujos_ofrece_las_recetas(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: [])
    monkeypatch.setattr(n8n, "ejecuciones", lambda **k: [])

    cuerpo = client.get("/ajustes/automatizaciones/").content.decode()
    assert "Todavía no hay ninguna" in cuerpo
    assert "Buzón de correo" in cuerpo, "no se ofrecieron las recetas"


# ── La lista ───────────────────────────────────────────────────────────────


def _flujo(**kw):
    base = {"id": "7", "nombre": "CFDI por correo", "activo": False,
            "pasos": 3, "disparador": "Email Trigger", "actualizado": "2026-08-24"}
    base.update(kw)
    return base


def test_pinta_el_disparador_y_la_ultima_corrida(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: [_flujo(activo=True)])
    monkeypatch.setattr(n8n, "ejecuciones", lambda **k: [
        {"id": "1", "flujo": "CFDI por correo", "estado": "success",
         "cuando": "2026-08-24 07:15"},
    ])

    cuerpo = client.get("/ajustes/automatizaciones/").content.decode()
    assert "Email Trigger" in cuerpo
    assert "2026-08-24 07:15" in cuerpo
    assert "Prendida" in cuerpo


def test_una_que_nunca_ha_corrido_lo_dice(client, jefe, monkeypatch):  # noqa: ARG001
    """Callarlo se lee como «corrió bien», que es la lectura peligrosa."""
    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "listar_flujos", lambda: [_flujo()])
    monkeypatch.setattr(n8n, "ejecuciones", lambda **k: [])

    cuerpo = client.get("/ajustes/automatizaciones/").content.decode()
    assert "todavía no ha corrido" in cuerpo


# ── El interruptor ─────────────────────────────────────────────────────────


def test_prender_llama_a_n8n_y_lo_confirma(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    llamadas = []
    monkeypatch.setattr(n8n, "activar", lambda fid: llamadas.append(fid) or True)

    r = client.post("/ajustes/automatizacion-interruptor" if False else
                    "/ajustes/automatizaciones/interruptor",
                    {"flujo_id": "7", "prender": "1", "nombre": "CFDI por correo"},
                    follow=True)
    assert llamadas == ["7"]
    assert "quedó prendida" in r.content.decode()


def test_si_n8n_se_niega_NO_se_dice_que_quedo_prendida(client, jefe, monkeypatch):  # noqa: ARG001
    """El modo de falla que importa: dar por hecho lo que no se comprobó."""
    from lib import n8n

    monkeypatch.setattr(n8n, "activar", lambda fid: False)

    r = client.post("/ajustes/automatizaciones/interruptor",
                    {"flujo_id": "7", "prender": "1", "nombre": "CFDI por correo"},
                    follow=True)
    cuerpo = r.content.decode()
    assert "quedó prendida" not in cuerpo
    assert "no aceptó" in cuerpo


def test_apagar_usa_el_camino_de_apagar(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    llamadas = []
    monkeypatch.setattr(n8n, "desactivar", lambda fid: llamadas.append(fid) or True)
    monkeypatch.setattr(n8n, "activar",
                        lambda fid: pytest.fail("apagar llamó a activar"))

    client.post("/ajustes/automatizaciones/interruptor",
                {"flujo_id": "7", "prender": "0", "nombre": "X"}, follow=True)
    assert llamadas == ["7"]


def test_el_interruptor_no_se_dispara_por_GET(client, jefe):  # noqa: ARG001
    assert client.get("/ajustes/automatizaciones/interruptor").status_code == 405


# ── Instalar una receta ────────────────────────────────────────────────────


def test_instalar_una_receta_la_crea_apagada(client, jefe, monkeypatch):  # noqa: ARG001
    """La tranca principal: nace apagada, siempre."""
    from lib import n8n

    capturado = {}

    def _crear(nombre, nodos, conexiones=None):
        capturado.update(nombre=nombre, nodos=nodos, conexiones=conexiones)
        return {"id": "9", "nombre": nombre, "activo": False}

    monkeypatch.setattr(n8n, "crear", _crear)

    r = client.post("/ajustes/automatizaciones/instalar",
                    {"plantilla": "buzon_a_despacho", "nombre": "Papeleo por correo"},
                    follow=True)
    cuerpo = r.content.decode()
    assert capturado["nombre"] == "Papeleo por correo"
    assert capturado["nodos"], "se creó un flujo sin pasos"
    assert "APAGADA" in cuerpo
    # Y `n8n.crear` es quien garantiza el apagado: el cuerpo que arma nunca
    # lleva `active`. Si alguien lo agregara, este test seguiría verde — por eso
    # existe además el candado de `tests/taller/test_crear_automatizacion.py`.


def test_una_receta_inventada_se_rechaza_con_nombres(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    monkeypatch.setattr(n8n, "crear",
                        lambda *a, **k: pytest.fail("no debió llegar a crear"))

    r = client.post("/ajustes/automatizaciones/instalar",
                    {"plantilla": "la_que_yo_quiera", "nombre": "X"}, follow=True)
    assert "No hay una receta" in r.content.decode()


def test_sin_nombre_no_se_crea(client, jefe, monkeypatch):  # noqa: ARG001
    from lib import n8n

    monkeypatch.setattr(n8n, "crear",
                        lambda *a, **k: pytest.fail("no debió llegar a crear"))
    r = client.post("/ajustes/automatizaciones/instalar",
                    {"plantilla": "buzon_a_despacho", "nombre": "  "}, follow=True)
    assert "nombre" in r.content.decode().lower()


def test_dice_lo_que_falta_hacer_a_mano(client, jefe, monkeypatch):  # noqa: ARG001
    """La receta del buzón no puede traer la cuenta de correo: sus credenciales
    viven en n8n. Callarlo deja un flujo que nunca va a correr."""
    from lib import n8n

    monkeypatch.setattr(n8n, "crear",
                        lambda n, nodos, conexiones=None: {"id": "9", "nombre": n})
    r = client.post("/ajustes/automatizaciones/instalar",
                    {"plantilla": "buzon_a_despacho", "nombre": "Buzón"}, follow=True)
    assert "cuenta de correo" in r.content.decode()


# ── El menú ────────────────────────────────────────────────────────────────


def test_esta_en_el_menu_de_gerencia():
    """Ojo con leerlo de una respuesta del cliente: el `DIRS` de las pruebas
    resuelve `sidebar.html` al de El Taller y saldría verde sin mirar el
    archivo que se prueba."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent
    menu = (raiz / "la-gerencia/templates/_componentes_tailadmin/sidebar.html").read_text()
    assert "ajustes-automatizaciones" in menu
    assert "Automatizaciones" in menu
    # Y el renglón padre no puede quedar marcado a la vez que el hijo.
    assert "'/ajustes/automatizaciones' in request.path %}menu-item-inactive" in menu
