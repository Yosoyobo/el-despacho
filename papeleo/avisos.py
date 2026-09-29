"""El aviso de «llegó papeleo nuevo», por El Interfón.

**A quién.** A quien tiene permiso de VER el papeleo (`papeleo.ver`) — decisión
de Oscar (Sep28). No a quien lo sube: el aviso existe para que alguien que no
estaba mirando se entere de que entró un contrato o una remisión.

**Cuándo.** Sólo si `ConfiguracionPapeleo.avisar_al_entrar` está prendido. Nace
apagado a propósito: si entran veinte remisiones un lunes, veinte avisos enseñan
al equipo a ignorarlos. Y cada persona puede silenciarlo en
`/perfil/notificaciones/` (categoría `papeleo`, opt-out como las demás).

**Cómo.** Igual que los demás push del repo: `on_commit` para no avisar de algo
que se deshizo, y `ejecutar_en_fondo` para que quien empujó el documento no
espere a que Apple y Google acusen recibo de los avisos de los demás. Del otro
lado de esta puerta hay un robot (n8n), y un robot al que se le hace esperar
termina reintentando.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

#: La categoría opt-out en `/perfil/notificaciones/`. Vive aquí para que el
#: catálogo de categorías y el envío no puedan escribirla distinto.
CATEGORIA = "papeleo"


def _debe_avisar() -> bool:
    try:
        from ajustes.models import ConfiguracionPapeleo

        return bool(ConfiguracionPapeleo.obtener().avisar_al_entrar)
    except Exception:  # noqa: BLE001 — sin configuración no se avisa
        return False


def avisar_papeleo_nuevo(*, nombre: str, titulo: str = "", tarea: str = "") -> bool:
    """Programa el aviso. Devuelve si se programó. Nunca lanza.

    `nombre` es el del archivo tal como llegó; `titulo`, el que mandó el robot
    si mandó uno. El aviso lleva a la pantalla del papeleo y no al documento:
    cuando esto corre el documento TODAVÍA NO EXISTE (Paperless devolvió el id de
    la tarea y su lector de texto corre después), así que no hay a qué enlazar.
    """
    if not _debe_avisar():
        return False

    etiqueta = (titulo or nombre or "un documento").strip()[:120]

    def _hacer():
        from lib.interfono import enviar_a_usuario
        from lib.permisos import usuarios_con_permiso

        for u in usuarios_con_permiso("papeleo", "ver"):
            try:
                enviar_a_usuario(
                    u,
                    titulo="📄 Llegó papeleo nuevo",
                    cuerpo=(f"«{etiqueta}» entró al archivo. En unos minutos se "
                            "puede buscar por lo que dice adentro."),
                    url="/papeleo/",
                    tag=f"papeleo-{tarea or etiqueta}"[:100],
                    categoria=CATEGORIA,
                    origen_modulo="papeleo",
                )
            except Exception:  # noqa: BLE001 — un aviso roto no tumba los demás
                logger.exception("papeleo: no se pudo avisar a usuario=%s", u.pk)

    def _al_confirmar():
        from lib.tareas_fondo import ejecutar_en_fondo

        ejecutar_en_fondo(_hacer)

    try:
        transaction.on_commit(_al_confirmar)
    except Exception:  # noqa: BLE001
        logger.exception("papeleo: no se pudo programar el aviso")
        return False
    return True


__all__ = ["CATEGORIA", "avisar_papeleo_nuevo"]
