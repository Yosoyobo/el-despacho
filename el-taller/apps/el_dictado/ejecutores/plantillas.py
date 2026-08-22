"""Ejecutores de plantillas de correo — El Chalán las redacta, un humano las suelta.

Una plantilla que El Chalán crea nace **apagada** (`activa=False`,
`origen="chalan"`). Decisión de Oscar, y la razón es concreta: el resto de los
ejecutores tocan datos internos, pero una plantilla termina en la bandeja de un
CLIENTE. Un texto mal redactado no puede salir por accidente, así que alguien
tiene que abrirla, leerla y encenderla en Ajustes → El Cartero → Plantillas.

Se apoya en el mismo permiso que enviar correos (`comunicacion.enviar_correo`):
quien puede escribirle a un cliente puede preparar el molde del correo.
"""

from __future__ import annotations

from . import _gate, registrar

# Un correo entero cabe de sobra; el tope es para que un LLM desbocado no meta
# medio megabyte de HTML en la base.
MAX_CUERPO = 20_000


def _exigir(condicion, mensaje: str) -> None:
    if not condicion:
        raise ValueError(mensaje)


def _slug_libre(base: str) -> str:
    from django.utils.text import slugify

    from ajustes.models import PlantillaCorreo

    raiz = (slugify(base) or "plantilla")[:36]
    slug, n = raiz, 2
    while PlantillaCorreo.objects.filter(slug=slug).exists():
        sufijo = f"-{n}"
        slug = raiz[: 40 - len(sufijo)] + sufijo
        n += 1
    return slug


@registrar("crear_plantilla_correo")
def crear_plantilla_correo(accion, usuario, contexto=None):  # noqa: ARG001
    """Payload: nombre, asunto?, cuerpo_html? | cuerpo?, descripcion?,
    remitente_email?, remitente_nombre?.

    Nace APAGADA: hay que revisarla y encenderla antes de poder mandarla.
    """
    _gate(usuario, "puede_enviar_correo", "crear plantillas de correo")
    from ajustes.models import PlantillaCorreo
    from lib.sanear import sanear_contexto

    payload = accion.payload or {}
    nombre = sanear_contexto((payload.get("nombre") or "").strip())[:120]
    _exigir(bool(nombre), "`nombre` requerido para la plantilla.")

    # El LLM manda el cuerpo con una llave u otra según cómo lo pida el usuario.
    cuerpo = (payload.get("cuerpo_html") or payload.get("cuerpo") or "").strip()
    _exigir(len(cuerpo) <= MAX_CUERPO,
            f"El cuerpo del correo es demasiado largo (máx. {MAX_CUERPO} caracteres).")

    remitente = (payload.get("remitente_email") or "").strip()
    if remitente:
        _exigir("@" in remitente and "." in remitente.split("@")[-1],
                f"«{remitente}» no parece un correo válido.")

    plantilla = PlantillaCorreo.objects.create(
        slug=_slug_libre(nombre),
        nombre=nombre,
        descripcion=sanear_contexto((payload.get("descripcion") or "").strip())[:200],
        asunto=sanear_contexto((payload.get("asunto") or "").strip())[:300],
        cuerpo_html=cuerpo,
        remitente_email=remitente,
        remitente_nombre=sanear_contexto(
            (payload.get("remitente_nombre") or "").strip()
        )[:120],
        # Lo que hace que esto sea seguro: no se puede mandar hasta revisarla.
        activa=False,
        origen="chalan",
        sistema=False,
        actualizado_por=usuario,
    )

    accion.entidad_tipo = "plantilla_correo"
    accion.entidad_id = plantilla.pk

    import contextlib
    with contextlib.suppress(Exception):
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="plantilla_correo.creada",
            actor_id=usuario.pk, actor_email=usuario.email,
            payload={"slug": plantilla.slug, "nombre": plantilla.nombre,
                     "origen": "chalan"},
        ))
