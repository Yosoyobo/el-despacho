"""El Chalán alcanza TODAS las herramientas instaladas (S-NUC-Servicios).

Oscar, 2026-08-24: «repasa que el MCP del Chalán pueda usar todas las
herramientas instaladas a la perfección. Si puedo clickear, teclear, lo puede
hacer el chalán».

Tenía razón y el hueco era grande: se instalaron cuatro piezas y sólo una —n8n—
estaba conectada al Chalán. Podía armar un PDF, medir una ruta por calles y
buscar en el archivo, y **no lo sabía**.

**El test que importa es el primero**: recorre las piezas que el servidor
declara y exige que cada una tenga al menos una capacidad. Si mañana se instala
algo nuevo y se olvida conectarlo, esto falla — que es exactamente lo que pasó
hoy y lo que no debe repetirse.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

#: Qué capacidad cubre cada pieza instalada. La llave es la del servicio en
#: `lib.site.servicios.PIEZAS`; el valor, lo que el Chalán puede hacer con ella.
COBERTURA = {
    "gotenberg": ["generar_pdf_cotizacion", "convertir_a_pdf"],
    "osrm": ["distancia_entre"],
    "n8n": ["listar_automatizaciones", "activar_automatizacion"],
    "paperless": ["buscar_papeleo", "archivar_documento"],
}


def _todo_lo_que_alcanza() -> set[str]:
    """Las capacidades del Chalán: lo que puede consultar y lo que puede proponer."""
    from apps.el_dictado.ejecutores import EJECUTORES

    # Importar `lecturas` es lo que las registra: el registro se llena al
    # importar el módulo, no al arrancar Django.
    import capacidades.lecturas  # noqa: F401
    from capacidades.registro import CAPACIDADES

    return set(CAPACIDADES) | set(EJECUTORES)


def test_cada_pieza_instalada_es_alcanzable():
    """El candado. Instalar algo y no conectarlo al Chalán es el error que se
    cometió hoy con tres de cuatro piezas."""
    from lib.site import servicios

    alcanza = _todo_lo_que_alcanza()
    for pieza in servicios.PIEZAS:
        clave = pieza["clave"]
        esperadas = COBERTURA.get(clave)
        assert esperadas, (
            f"«{pieza['nombre']}» está instalada pero nadie declaró qué puede hacer "
            f"el Chalán con ella. Agrégala a COBERTURA y dale sus capacidades."
        )
        faltantes = [c for c in esperadas if c not in alcanza]
        assert not faltantes, f"«{pieza['nombre']}»: al Chalán le faltan {faltantes}"


def test_no_se_declaran_capacidades_fantasma():
    """Al revés: que COBERTURA no prometa piezas que no existen."""
    from lib.site import servicios

    instaladas = {p["clave"] for p in servicios.PIEZAS}
    sobran = set(COBERTURA) - instaladas
    assert not sobran, f"COBERTURA menciona piezas que no están instaladas: {sobran}"


# ── Que se puedan llamar DE VERDAD, no sólo que existan ────────────────────


def test_toda_capacidad_registrada_tiene_la_firma_del_registro():
    """El registro despacha SIEMPRE `cap.fn(args, usuario)` — posicional.

    Una capacidad escrita `(usuario, **kw)` no falla al registrarse ni en un
    test que la llame directo: falla EN PRODUCCIÓN, donde el primer argumento
    le llega como si fuera el usuario. Pasó DOS veces el mismo día (2026-08-24):
    mis tres herramientas del servidor, y las tres de n8n de otra sesión — que
    vivieron rotas cuatro días porque su test las llamaba con su propia
    convención. La introspección de firma caza la clase entera del bug, sin
    red y sin base: el primer parámetro posicional de todo `fn` se llama `args`.
    """
    import inspect

    import capacidades.lecturas  # noqa: F401 — importar es lo que registra
    from capacidades.registro import CAPACIDADES

    mal = []
    for nombre, cap in CAPACIDADES.items():
        params = [p for p in inspect.signature(cap.fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(params) < 2 or params[0].name != "args":
            mal.append(f"{nombre} → fn({', '.join(p.name for p in params)}…)")
    assert not mal, (
        "Capacidades con la firma invertida — en producción reciben los args "
        "como usuario y el usuario como args:\n  " + "\n  ".join(mal)
    )



def test_las_capacidades_nuevas_se_invocan_como_las_llama_el_registro(monkeypatch,
                                                                      usuario_factory):
    """El registro llama `fn(args, usuario)`. Una capacidad escrita con otra
    firma pasa todos los tests que la llaman directo y **falla en producción**:
    el primer argumento le llega como si fuera el usuario. Este test la ejerce
    por el mismo camino que el Chalán."""
    import capacidades.lecturas  # noqa: F401
    from capacidades.registro import CAPACIDADES
    from lib import ruteo

    monkeypatch.setattr(ruteo, "distancia", lambda a, b: 20399.1)
    monkeypatch.setattr(ruteo, "ultima_fuente", lambda: ruteo.FUENTE_CALLES)

    cap = CAPACIDADES["distancia_entre"]
    r = cap.fn({"origen": "19.4326,-99.1332", "destino": "19.5094,-99.2386"},
               usuario_factory(rol="super_admin"))
    assert r["km"] == 20.4


def test_puede_medir_una_distancia_por_calle(monkeypatch, usuario_factory):
    from capacidades.lecturas import _h_distancia_entre
    from lib import ruteo

    monkeypatch.setattr(ruteo, "distancia", lambda a, b: 20399.1)
    monkeypatch.setattr(ruteo, "ultima_fuente", lambda: ruteo.FUENTE_CALLES)

    r = _h_distancia_entre({"origen": "19.4326,-99.1332",
                            "destino": "19.5094,-99.2386"},
                           usuario_factory(rol="super_admin"))
    assert r["km"] == 20.4
    assert "calles" in r["medido"]


def test_avisa_cuando_midio_en_linea_recta(monkeypatch, usuario_factory):
    """Un número sin decir cómo se midió engaña: 14 km en recta y 20 por calle
    son la misma pregunta con dos respuestas."""
    from capacidades.lecturas import _h_distancia_entre
    from lib import ruteo

    monkeypatch.setattr(ruteo, "distancia", lambda a, b: 14000.0)
    monkeypatch.setattr(ruteo, "ultima_fuente", lambda: ruteo.FUENTE_RECTA)

    r = _h_distancia_entre({"origen": "19.4326,-99.1332",
                            "destino": "19.5094,-99.2386"},
                           usuario_factory(rol="super_admin"))
    assert "línea recta" in r["medido"]
    assert r["nota"], "no dijo que el número queda corto"


def test_unas_coordenadas_mal_escritas_se_avisan(usuario_factory):
    from capacidades.lecturas import _h_distancia_entre

    r = _h_distancia_entre({"origen": "por allá", "destino": "19.5,-99.2"},
                           usuario_factory(rol="super_admin"))
    assert "error" in r


def test_puede_decir_que_herramientas_responden(monkeypatch, usuario_factory):
    from capacidades.lecturas import _h_estado_herramientas
    from lib.site import servicios

    monkeypatch.setattr(servicios, "_http", lambda url, **k: True)
    r = _h_estado_herramientas({}, usuario_factory(rol="miembro"))
    assert r["resumen"]["total"] == len(servicios.PIEZAS)
    assert all("para_que" in p for p in r["piezas"]), "no dice para qué sirve cada una"


# ── Y que lo nuevo esté en los tres lugares ────────────────────────────────


def test_las_acciones_nuevas_estan_completas():
    from pathlib import Path

    from apps.el_dictado.ejecutores import EJECUTORES

    from lib.dictado_catalogo import COMANDOS_DICTADO

    raiz = Path(__file__).resolve().parent.parent.parent
    prompt = (raiz / "el-taller/apps/el_dictado/prompt.py").read_text()
    catalogo = {c["tipo"] for c in COMANDOS_DICTADO}

    for tipo in ("generar_pdf_cotizacion", "archivar_documento", "convertir_a_pdf"):
        assert tipo in EJECUTORES, f"{tipo}: falta el ejecutor"
        assert tipo in catalogo, f"{tipo}: falta en el catálogo"
        assert tipo in prompt, f"{tipo}: falta en el prompt"


def test_cada_comando_del_catalogo_tiene_un_gating_que_existe():
    """Un `gating` mal escrito no falla: `comandos_para` cae a `None` y el
    comando se le ofrece a TODO EL MUNDO. Se ve bien y abre una puerta."""
    from lib.dictado_catalogo import COMANDOS_DICTADO, _gating_checks

    conocidos = set(_gating_checks())
    huerfanos = sorted({c["gating"] for c in COMANDOS_DICTADO
                        if c.get("gating") and c["gating"] not in conocidos})
    assert not huerfanos, f"gating sin comprobación (se ofrecerían a cualquiera): {huerfanos}"
