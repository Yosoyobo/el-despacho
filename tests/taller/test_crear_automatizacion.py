"""El Chalán crea automatizaciones — y los guardrails que lo hacen intentable.

Oscar: «si podemos intentar que el chalán haga flujos desde cero, vamos a ver
qué puede hacer con los guardrails que pusimos» (2026-08-24).

La objeción que tenía esto cerrado sigue siendo cierta: un modelo inventando un
grafo de n8n produce, casi siempre, algo que se ve bien y no corre. Lo que
cambia no es la objeción, son las tres trancas — y esto las fija:

1. **Nace apagada.** Lo único que hace peligrosa a una automatización es estar
   prendida (le escribe a clientes). Un flujo apagado es un borrador.
2. **Se revisa y se dice la verdad.** n8n GUARDA sin quejarse un nodo cuyo tipo
   no existe. Sin revisión, «creada con éxito» sería mentira.
3. **Sin permiso no pasa**, aunque el prompt la haya propuesto.
"""

from __future__ import annotations

import pytest

from lib import n8n_plantillas

# ── Las recetas ─────────────────────────────────────────────────────────────


def test_las_tres_recetas_se_arman_con_su_disparador_y_conectadas():
    """Una receta que no arranca sola o no está conectada no sirve de nada."""
    for nombre in n8n_plantillas.PLANTILLAS:
        nodos, conexiones = n8n_plantillas.armar(nombre)
        assert n8n_plantillas.revisar(nodos, conexiones) == [], nombre


def test_los_nodos_de_las_recetas_usan_tipos_que_conocemos():
    for nombre in n8n_plantillas.PLANTILLAS:
        nodos, _ = n8n_plantillas.armar(nombre)
        for n in nodos:
            assert n["type"] in n8n_plantillas.TIPOS_CONOCIDOS, (nombre, n["type"])


def test_la_version_del_nodo_sale_del_catalogo_y_no_del_modelo():
    """Una typeVersion más alta que la instalada deja el nodo roto en el editor,
    y ése es el error que nadie nota hasta que el flujo no corre."""
    nodos, _ = n8n_plantillas.armar("programado_a_despacho")
    for n in nodos:
        assert n["typeVersion"] == n8n_plantillas.TIPOS_CONOCIDOS[n["type"]][0]


def test_las_conexiones_se_refieren_a_los_nodos_por_su_nombre_real():
    """Se arman a partir de la propia lista para que no se desincronicen."""
    nodos, conexiones = n8n_plantillas.armar("buzon_a_despacho")
    nombres = {n["name"] for n in nodos}
    for origen, salidas in conexiones.items():
        assert origen in nombres
        for rama in salidas["main"]:
            for destino in rama:
                assert destino["node"] in nombres


def test_la_receta_del_buzon_apunta_a_el_despacho_por_la_red_de_docker():
    """Desde dentro del contenedor, la dirección del tailnet daría la vuelta
    por la red para volver al mismo lugar."""
    nodos, _ = n8n_plantillas.armar("buzon_a_despacho",
                                    {"ruta": "/papeleo/entra"})
    url = nodos[1]["parameters"]["url"]
    assert url == "http://el-taller:8000/papeleo/entra"
    assert "100.121" not in url


def test_la_receta_del_buzon_manda_el_token_en_su_cabecera():
    nodos, _ = n8n_plantillas.armar(
        "buzon_a_despacho", {"cabecera_token": "x-papeleo-token", "token": "secreto"})
    cabeceras = nodos[1]["parameters"]["headerParameters"]["parameters"]
    assert {"name": "x-papeleo-token", "value": "secreto"} in cabeceras


def test_sin_token_la_receta_deja_un_hueco_visible_en_vez_de_uno_vacio():
    """Un valor vacío se ve igual que uno correcto; un hueco con texto no."""
    nodos, _ = n8n_plantillas.armar("buzon_a_despacho")
    valor = nodos[1]["parameters"]["headerParameters"]["parameters"][0]["value"]
    assert "PEGA" in valor


def test_una_receta_inexistente_dice_cuales_hay():
    with pytest.raises(ValueError, match="buzon_a_despacho"):
        n8n_plantillas.armar("la_que_se_me_ocurrio")


# ── La revisión: lo que evita mentir ────────────────────────────────────────


def test_avisa_del_nodo_cuyo_tipo_no_existe():
    """El caso que justifica todo: n8n lo guarda sin error y no corre."""
    nodos = [{"name": "Inventado", "type": "n8n-nodes-base.mandarWhatsapp",
              "typeVersion": 1, "parameters": {}}]
    avisos = n8n_plantillas.revisar(nodos, {})
    assert any("no conozco" in a for a in avisos)


def test_avisa_cuando_nada_hace_arrancar_el_flujo():
    nodos = [{"name": "Llamar", "type": "n8n-nodes-base.httpRequest",
              "typeVersion": 4.2, "parameters": {}}]
    assert any("arrancar" in a for a in n8n_plantillas.revisar(nodos, {}))


def test_avisa_cuando_los_pasos_no_estan_conectados():
    nodos, _ = n8n_plantillas.armar("programado_a_despacho")
    assert any("conectados" in a for a in n8n_plantillas.revisar(nodos, {}))


def test_avisa_de_dos_pasos_con_el_mismo_nombre():
    """Las conexiones de n8n son por nombre: dos iguales las confunden."""
    nodos, conexiones = n8n_plantillas.armar("programado_a_despacho")
    nodos[1]["name"] = nodos[0]["name"]
    assert any("dos pasos" in a for a in n8n_plantillas.revisar(nodos, conexiones))


def test_un_flujo_sin_pasos_no_pasa_por_bueno():
    assert n8n_plantillas.revisar([], {}) != []


# ── El ejecutor ─────────────────────────────────────────────────────────────


@pytest.fixture
def jefe(db):
    from cuentas.models.usuario import Usuario

    return Usuario.objects.create_user(email="jefe@lc.mx", password="x",
                                       nombre_completo="Jefe", rol="super_admin")


@pytest.fixture
def n8n_falso(monkeypatch):
    """Un n8n que acepta lo que le manden y recuerda con qué lo llamaron."""
    from lib import n8n

    registro: dict = {}

    def _crear(nombre, nodos, conexiones=None):
        registro["nombre"] = nombre
        registro["nodos"] = nodos
        registro["conexiones"] = conexiones
        return {"id": "77", "nombre": nombre, "activo": False,
                "pasos": len(nodos), "disparador": "manual", "actualizado": ""}

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "crear", _crear)
    monkeypatch.setattr(n8n, "detalle_flujo",
                        lambda fid: {"id": fid, "pasos": len(registro["nodos"])})
    return registro


def _accion(payload: dict):
    class _A:
        pass

    a = _A()
    a.payload = payload
    return a


@pytest.mark.django_db
def test_crear_con_receta_arma_el_flujo_y_avisa_que_queda_apagada(jefe, n8n_falso):
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    r = crear_automatizacion(
        _accion({"nombre": "Papeleo por correo", "plantilla": "buzon_a_despacho",
                 "params": {"token": "abc"}}), jefe)
    assert r["entidad_id"] == "77"
    assert "APAGADA" in r["resumen"]
    assert n8n_falso["nombre"] == "Papeleo por correo"
    assert len(n8n_falso["nodos"]) == 2


@pytest.mark.django_db
def test_la_receta_avisa_de_lo_que_falta_hacer_a_mano(jefe, n8n_falso):  # noqa: ARG001
    """Sin decirlo, el usuario cree que ya quedó y el flujo nunca corre."""
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    r = crear_automatizacion(
        _accion({"nombre": "Buzón", "plantilla": "buzon_a_despacho"}), jefe)
    assert "cuenta de correo" in r["resumen"]


@pytest.mark.django_db
def test_crear_libre_se_permite_pero_el_resumen_no_miente(jefe, n8n_falso):  # noqa: ARG001
    """El experimento que pidió Oscar: el grafo inventado SÍ se crea, y el
    resumen dice que hay que revisarlo."""
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    r = crear_automatizacion(_accion({
        "nombre": "Invento",
        "nodos": [{"name": "Raro", "type": "n8n-nodes-base.telepatia",
                   "parameters": {}}],
        "conexiones": {},
    }), jefe)
    assert "APAGADA" in r["resumen"]
    assert "no conozco" in r["resumen"]


@pytest.mark.django_db
def test_sin_nombre_no_se_crea(jefe, n8n_falso):  # noqa: ARG001
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    with pytest.raises(ValueError, match="nombre"):
        crear_automatizacion(_accion({"plantilla": "buzon_a_despacho"}), jefe)


@pytest.mark.django_db
def test_sin_receta_ni_pasos_dice_que_recetas_hay(jefe, n8n_falso):  # noqa: ARG001
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    with pytest.raises(ValueError, match="buzon_a_despacho"):
        crear_automatizacion(_accion({"nombre": "Vacía"}), jefe)


@pytest.mark.django_db
def test_sin_permiso_no_crea_aunque_el_chalan_lo_proponga(n8n_falso):  # noqa: ARG001
    """Defensa en profundidad: el prompt filtra por rol, esto es la puerta."""
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    from cuentas.models.usuario import Usuario

    nadie = Usuario.objects.create_user(email="nadie@lc.mx", password="x",
                                        nombre_completo="Nadie", rol="miembro")
    with pytest.raises(ValueError, match="permiso"):
        crear_automatizacion(
            _accion({"nombre": "X", "plantilla": "buzon_a_despacho"}), nadie)


@pytest.mark.django_db
def test_sin_llave_de_n8n_lo_dice_en_lugar_de_tronar(jefe, monkeypatch):
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: False)
    with pytest.raises(ValueError, match="llave de n8n"):
        crear_automatizacion(
            _accion({"nombre": "X", "plantilla": "buzon_a_despacho"}), jefe)


@pytest.mark.django_db
def test_si_n8n_no_pudo_crear_no_se_reporta_exito(jefe, monkeypatch):
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    from lib import n8n

    monkeypatch.setattr(n8n, "esta_configurado", lambda: True)
    monkeypatch.setattr(n8n, "crear", lambda *a, **k: None)
    with pytest.raises(ValueError, match="no pudo crear"):
        crear_automatizacion(
            _accion({"nombre": "X", "plantilla": "buzon_a_despacho"}), jefe)


# ── El contrato de los tres lugares ─────────────────────────────────────────


def test_el_ejecutor_esta_registrado():
    from apps.el_dictado import ejecutores

    assert "crear_automatizacion" in ejecutores.EJECUTORES


def test_esta_en_el_catalogo_del_dictado_con_su_gating():
    from lib.dictado_catalogo import COMANDOS_DICTADO

    fila = next(c for c in COMANDOS_DICTADO if c["tipo"] == "crear_automatizacion")
    assert fila["gating"] == "automatizacion"


def test_el_prompt_lo_anuncia_y_manda_preferir_una_receta():
    from apps.el_dictado.prompt import SYSTEM_PROMPT

    assert "crear_automatizacion" in SYSTEM_PROMPT
    assert "listar_recetas_automatizacion" in SYSTEM_PROMPT


def test_la_capacidad_de_las_recetas_existe_y_no_necesita_llave():
    """Es el catálogo del repo, no una consulta a n8n: sirve sin configurar nada."""
    from capacidades.registro import CAPACIDADES

    cap = CAPACIDADES["listar_recetas_automatizacion"]
    salida = cap.fn({}, None)
    assert len(salida["recetas"]) == len(n8n_plantillas.PLANTILLAS)


# ── El guardrail que no se puede perder ─────────────────────────────────────


def test_el_cuerpo_que_se_manda_a_n8n_nunca_pide_activarla(monkeypatch):
    """Si alguien agregara `active: True` al cuerpo, el flujo nacería prendido y
    empezaría a escribirle a clientes antes de que nadie lo mire. Nada en la
    pantalla lo delataría: por eso el candado está aquí."""
    from lib import n8n

    visto: dict = {}

    def _pedir(ruta, *, metodo="GET", cuerpo=None):
        visto["cuerpo"] = cuerpo
        return {"id": "1", "name": "x", "nodes": [], "active": False}

    monkeypatch.setattr(n8n, "llave", lambda: "k")
    monkeypatch.setattr(n8n, "_pedir", _pedir)
    n8n.crear("Prueba", [{"name": "a", "type": "n8n-nodes-base.noOp"}])
    assert visto["cuerpo"].get("active") in (None, False)


def test_crear_no_prende_la_automatizacion_de_pasada(monkeypatch, jefe, n8n_falso):  # noqa: ARG001
    """Crear y prender son dos acciones, y cada una pide su confirmación."""
    from apps.el_dictado.ejecutores.automatizacion import crear_automatizacion

    from lib import n8n

    def _no(*a, **k):  # pragma: no cover
        raise AssertionError("crear no debe activar nada")

    monkeypatch.setattr(n8n, "activar", _no)
    crear_automatizacion(
        _accion({"nombre": "X", "plantilla": "programado_a_despacho"}), jefe)
