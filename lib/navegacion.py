"""A dónde regresar después de guardar — regla única de El Taller.

LC 2026-08-12 (Oscar): «Al darle guardar en la pág. de un producto me saca a
la lista. Al eliminar un producto de la lista igual me saca. Esto seguro
sucede en muchas otras partes — revisar y parchar universalmente.»

La regla es simple: **guardar te deja donde estás**. Editar una ficha la
recarga; archivar o eliminar desde una lista te devuelve a la lista *con tus
filtros puestos*, no a la lista pelona.

Antes el repo tenía cuatro mecanismos distintos que no compartían contrato
(`_next_seguro` de Tesorería, `_destino_registro` de Proyectos,
`_navegacion_producto` del Catálogo, y el `?volver=` que sólo se leía al pintar
el encabezado, nunca al redirigir). Aquí queda uno solo.

No lanza nunca: sin destino válido, devuelve el fallback.
"""

from __future__ import annotations

# Los nombres que puede traer el parámetro, en orden de preferencia.
LLAVES = ("volver", "next")


def es_ruta_interna(valor) -> bool:
    """¿Es una ruta relativa de esta app y no un salto a otro dominio?

    Se exige que empiece con una sola `/`: `//evil.com` es una URL de esquema
    relativo y el navegador la trataría como externa. Y sin saltos de línea,
    que abrirían la puerta a inyectar cabeceras.
    """
    if not valor:
        return False
    v = str(valor).strip()
    return (
        v.startswith("/")
        and not v.startswith("//")
        and "\n" not in v
        and "\r" not in v
        and "\\" not in v
    )


def destino_de_regreso(request, fallback: str) -> str:
    """La URL a la que mandar al usuario tras un POST, o `fallback`.

    Busca `volver` y `next` primero en el POST (los forms los llevan como campo
    oculto) y luego en la query string. Un destino externo se descarta en
    silencio — el fallback siempre es una ruta nuestra.
    """
    for fuente in (getattr(request, "POST", None), getattr(request, "GET", None)):
        if not fuente:
            continue
        for llave in LLAVES:
            valor = fuente.get(llave)
            if es_ruta_interna(valor):
                return str(valor).strip()
    return fallback


def con_volver(url: str, request) -> str:
    """`url` con `?volver=<la página actual>` pegado, para que el destino sepa
    regresar. Si la actual no es una ruta interna (raro), devuelve `url` tal cual.
    """
    from urllib.parse import quote

    actual = getattr(request, "get_full_path", lambda: "")()
    if not es_ruta_interna(actual):
        return url
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}volver={quote(actual, safe='')}"
