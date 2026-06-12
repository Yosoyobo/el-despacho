"""Widget AI 🤖 reusable del Taller — El Chalán redacta texto en cualquier
campo (comentarios, notas, respuestas del Buzón). Estación `redaccion_asistida`.

Estilo Copilot: el usuario escribe una instrucción ("redacta el avance de
#LC-0001 para @oscar"), El Chalán propone el texto y el usuario lo revisa/edita
antes de guardar (el submit normal del form publica).

Clave (Fin #1 + Fin #2 de S-Chalanes-UX): las referencias `@persona`,
`#PROYECTO`/`#LC-0001`, `$cliente` que el usuario ya escribió se RESUELVEN a
datos reales y se inyectan al prompt, para que El Chalán lea la entidad y
redacte con información correcta. Los tokens `@#$` se PRESERVAN en la salida
para que sigan siendo rastreables.

Diseño defensivo: nunca lanza — devuelve `{ok, texto, error}`.
"""

from __future__ import annotations

import re

_SYSTEM = """\
Eres El Chalán de Learning Center, un despacho mexicano de diseño y maquila.
Redactas TEXTO PLANO en español de México para un campo de un sistema interno
(un comentario, una nota o la respuesta a un mensaje).

REGLAS ESTRICTAS:
1. Devuelve SOLO el texto pedido, sin comillas, sin ```, sin encabezados ni
   firmas. Texto plano — nada de HTML ni Markdown de tablas.
2. PRESERVA EXACTAMENTE las referencias que el usuario escribió: @persona,
   #PROYECTO o #LC-0001, $cliente. No las traduzcas ni inventes nuevas; si
   mencionas a una persona/proyecto/cliente que ya viene referenciado, usa su
   token tal cual (ej. @oscar, #LC-0001).
3. Tono profesional y cordial, conciso, directo. Español de México.
4. Usa SOLO la información de [REFERENCIAS RESUELTAS] y [CONTEXTO] de abajo;
   no inventes datos, cifras ni nombres que no estén ahí.
"""

_RE_FENCE = re.compile(r"^```(?:\w+)?|```$", re.IGNORECASE | re.MULTILINE)
_RE_HTML = re.compile(r"<[^>]+>")

# Estaciones que el widget 🤖 puede invocar. El cliente manda `estacion`; se
# valida AQUÍ (server-side) — un valor fuera de la allowlist cae al default
# para que nadie enrute presupuesto/voz a una estación arbitraria.
_ESTACIONES_PERMITIDAS = {"redaccion_asistida", "cotizaciones"}
_ESTACION_DEFAULT = "redaccion_asistida"


def _limpiar(texto: str) -> str:
    """Salida = texto plano. Quita fences y cualquier etiqueta HTML."""
    texto = _RE_FENCE.sub("", texto or "").strip()
    texto = _RE_HTML.sub("", texto)
    # comillas envolventes que a veces agrega el modelo
    if len(texto) >= 2 and texto[0] in "\"'“" and texto[-1] in "\"'”":
        texto = texto[1:-1].strip()
    return texto.strip()


def bloque_referencias(*textos: str) -> str:
    """Resuelve @#$ de uno o más textos a entidades reales. Reusa el
    parser/resolver de `referencias`. Devuelve "" si no hay tokens o falla."""
    try:
        from referencias.parser import extraer_tokens
        from referencias.resolver import resolver_tokens
    except Exception:  # noqa: BLE001
        return ""
    junto = "\n".join(t for t in textos if t)
    tokens = extraer_tokens(junto)
    if not tokens:
        return ""
    resuelto = resolver_tokens(tokens)
    lineas: list[str] = []
    vistos: set[tuple] = set()
    for t in tokens:
        clave = (t.tipo, t.slug)
        if clave in vistos:
            continue
        vistos.add(clave)
        obj = resuelto.get(clave)
        sig = f"{t.sigil}{t.slug}"
        if obj is None:
            lineas.append(f"{sig} → (no encontrado)")
        elif t.tipo == "proyecto":
            estado = getattr(obj, "get_estado_display", lambda: "")()
            lineas.append(f"{sig} → proyecto {obj.codigo} «{obj.nombre}» estado: {estado}")
        elif t.tipo == "cliente":
            lineas.append(f"{sig} → cliente «{obj.razon_social}»")
        elif t.tipo == "usuario":
            nombre = getattr(obj, "nombre_completo", "") or obj.email
            lineas.append(f"{sig} → persona {nombre}")
    if not lineas:
        return ""
    return ("[REFERENCIAS RESUELTAS — datos reales de lo que el usuario mencionó]\n"
            + "\n".join(lineas))


def redactar(*, instruccion: str, texto_actual: str = "", contexto: dict | None = None,
             usuario=None, estacion: str = _ESTACION_DEFAULT) -> dict:
    """Genera/mejora el texto de un campo. Devuelve `{ok, texto, error}`.

    - `instruccion`: lo que el usuario quiere ("redacta el avance para @oscar").
    - `texto_actual`: lo ya escrito en el campo (puede estar vacío).
    - `contexto`: dict acotado, RESUELTO EN SERVIDOR por el endpoint a partir de
      (modelo, pk) — nunca confiar en contexto enviado por el cliente.
    - `estacion`: estación del Cuadro a usar (define proveedor/modelo/voz/
      presupuesto). Validada contra `_ESTACIONES_PERMITIDAS`; fuera de la
      allowlist cae al default. Ej. `cotizaciones` para redactar términos/notas
      de una cotización con su propia voz.
    """
    estacion = estacion if estacion in _ESTACIONES_PERMITIDAS else _ESTACION_DEFAULT
    instruccion = (instruccion or "").strip()
    if not instruccion:
        return {"ok": False, "texto": "", "error": "Escribe qué quieres que redacte El Chalán."}

    partes: list[str] = []
    refs = bloque_referencias(texto_actual, instruccion)
    if refs:
        partes.append(refs)
    if contexto:
        ctx_txt = "\n".join(f"- {k}: {v}" for k, v in contexto.items() if v not in (None, ""))
        if ctx_txt:
            partes.append("[CONTEXTO DEL CAMPO]\n" + ctx_txt)
    partes.append("[TEXTO ACTUAL DEL CAMPO]\n" + (texto_actual or "(vacío — créalo desde cero)"))
    partes.append("[LO QUE QUIERE EL USUARIO]\n" + instruccion)
    partes.append("Devuelve el texto final del campo, listo para guardar.")
    user_prompt = "\n\n".join(partes)

    try:
        from chalanes.voz import preludio
        from lib.analistas import analizar
        from lib.sanear import sanear_contexto
        prompt = (preludio(estacion) + _SYSTEM + "\n\n"
                  + sanear_contexto(user_prompt, max_len=8000))
        res = analizar(estacion=estacion, prompt=prompt,
                       max_tokens=800, temperatura=0.5,
                       actor_id=getattr(usuario, "pk", None))
    except Exception as exc:  # noqa: BLE001 — nunca tumbar la UI
        return {"ok": False, "texto": "", "error": f"El Chalán no respondió: {exc}"}

    texto = _limpiar(res.texto)
    if not texto:
        return {"ok": False, "texto": "", "error": "El Chalán devolvió un resultado vacío."}
    return {"ok": True, "texto": texto, "error": ""}


__all__ = ["redactar", "bloque_referencias"]
