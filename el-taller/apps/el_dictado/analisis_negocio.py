"""El Chalán OPINA del negocio de forma proactiva (S-Chalan-Negocio-V1).

Por dominio (finanzas, cobranza, ventas, márgenes) reúne los HECHOS reales
(`taller_home.negocio`), los funda en el conocimiento aprobado del negocio
(`conocimiento.bloque_contexto_negocio`) y le pide al Chalán una OPINIÓN
ejecutiva (observaciones + recomendaciones). El resultado se persiste
reutilizando `PropuestaChalan` (tipo `analisis_<dominio>`) y se empuja por El
Interfón, así aterriza en la tabla de notificaciones; la fila es clickeable y
abre un modal con el análisis completo.

Diseño:
- **Una sola llamada IA por dominio** (no por usuario): el análisis es del
  negocio, no personal. Se genera una vez (actor de sistema, sin tope) y se
  reparte a los destinatarios con permiso del dominio.
- **Idempotente por semana** (`clave_dedup=analisis_<dominio>:<YYYY-Www>:<uid>`):
  re-correr el cron no duplica.
- **Informativo**: opina/recomienda, NO propone acciones (sin Dictado). Si en
  el futuro se quieren acciones, se materializan con el flujo existente.
- **Defensivo**: IA caída / sin datos → no crea nada, nunca lanza.
"""

from __future__ import annotations

import logging
from datetime import date

from django.db import IntegrityError

logger = logging.getLogger(__name__)

ESTACION = "analisis_negocio"
CATEGORIA_PUSH = "chalan_analisis"

# Permiso requerido por dominio (lib.permisos). Solo recibe quien puede verlo.
DOMINIO_PERMISO = {
    "finanzas": "puede_ver_finanzas",
    "cobranza": "puede_ver_finanzas",
    "ventas": "puede_ver_cotizaciones",
    "margenes": "puede_ver_finanzas",
}

_SYSTEM = """\
Eres El Chalán de El Despacho (Learning Center, diseño/maquila B2B mexicano),
actuando como ASESOR de negocio. Te paso HECHOS reales del sistema (no inventes
ni cambies cifras: usa solo lo dado). Da una OPINIÓN EJECUTIVA breve y útil para
un dueño/contador, en español claro:

- 2 a 4 OBSERVACIONES (qué está pasando, qué destaca, qué preocupa).
- 1 a 3 RECOMENDACIONES accionables y concretas.
- Si todo está sano, dilo con franqueza (no inventes problemas).

Puedes usar viñetas con "- ". Sin tablas ni markdown pesado. Máximo ~180
palabras. NO propongas ejecutar acciones en el sistema: solo opinas y
recomiendas; el equipo decide. No saludes ni te despidas: ve al grano.
"""


def _destinatarios(dominio: str):
    """Usuarios activos con permiso para ver este dominio."""
    from cuentas.models.usuario import Usuario
    from lib import permisos

    check = getattr(permisos, DOMINIO_PERMISO.get(dominio, ""), None)
    if check is None:
        return []
    return [u for u in Usuario.objects.filter(is_active=True) if check(u)]


def _generar(dominio: str, hechos: dict) -> str:
    """Una llamada al Chalán → texto de opinión. "" si falla. Actor de sistema."""
    from chalanes.voz import preludio, reglas

    from .conocimiento import bloque_contexto_negocio

    partes = [
        preludio(ESTACION),
        _SYSTEM,
        bloque_contexto_negocio(dominio),
        reglas(),
        f"[DOMINIO]\n{hechos['titulo']}\n\n[HECHOS]\n{hechos['hechos']}",
    ]
    prompt = "\n\n".join(p for p in partes if p)
    try:
        from lib.analistas import analizar
        res = analizar(estacion=ESTACION, prompt=prompt, max_tokens=600,
                       temperatura=0.3, actor_id=None)
    except Exception:  # noqa: BLE001 — TodosFallaron, red, etc.
        logger.warning("análisis de negocio (%s): IA falló", dominio, exc_info=True)
        return ""
    return (res.texto or "").strip()


def _semana_iso() -> str:
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _persistir_y_push(usuario, dominio: str, titulo: str, texto: str):
    """Crea la PropuestaChalan del usuario (idempotente) y la empuja. None si ya existía."""
    from .models import PropuestaChalan

    clave = f"analisis_{dominio}:{_semana_iso()}:{usuario.pk}"
    if PropuestaChalan.objects.filter(usuario=usuario, clave_dedup=clave).exists():
        return None
    try:
        prop = PropuestaChalan.objects.create(
            usuario=usuario, tipo=f"analisis_{dominio}", clave_dedup=clave,
            titulo=titulo[:160], cuerpo=texto, url="", estado="pendiente",
        )
    except IntegrityError:
        return None
    prop.url = f"/chalan/analisis/{prop.pk}/"
    prop.save(update_fields=["url"])
    _push(usuario, titulo=titulo, cuerpo=texto, url=prop.url, clave=clave, origen_id=prop.pk)
    return prop


def _push(usuario, *, titulo: str, cuerpo: str, url: str, clave: str, origen_id: int) -> None:
    from lib.interfono import enviar_a_usuario
    try:
        enviar_a_usuario(
            usuario, titulo=f"📊 {titulo}", cuerpo=cuerpo[:160], url=url,
            tag=f"analisis-{clave}", categoria=CATEGORIA_PUSH,
            origen_modulo="chalan", origen_id=origen_id,
        )
    except Exception:  # noqa: BLE001 — un push roto no debe romper el cron
        logger.exception("push de análisis de negocio falló u=%s", getattr(usuario, "pk", None))


def analizar_dominio(*, dominio: str, dry_run: bool = False) -> dict:
    """Genera la opinión del dominio y la reparte. Devuelve un resumen."""
    from apps.taller_home import negocio

    base = {"ok": True, "dominio": dominio, "creadas": 0, "dry_run": dry_run,
            "texto": "", "motivo": ""}

    hechos = negocio.hechos_de(dominio)
    if not hechos.get("hechos"):
        base["ok"], base["motivo"] = False, "sin_datos"
        return base

    texto = _generar(dominio, hechos)
    if not texto:
        base["ok"], base["motivo"] = False, "fallo_ia"
        return base
    base["texto"] = texto

    titulo = f"El Chalán opina: {hechos['titulo']}"
    if dry_run:
        base["destinatarios"] = len(_destinatarios(dominio))
        return base

    creadas = 0
    for u in _destinatarios(dominio):
        if _persistir_y_push(u, dominio, titulo, texto):
            creadas += 1
    base["creadas"] = creadas
    _emitir(dominio, creadas)
    return base


def analizar_todo(*, dry_run: bool = False) -> dict[str, dict]:
    from apps.taller_home.negocio import DOMINIOS
    return {d: analizar_dominio(dominio=d, dry_run=dry_run) for d in DOMINIOS}


def _emitir(dominio: str, creadas: int) -> None:
    try:
        from lib.portavoz import emitir
        from lib.portavoz_eventos import EventoPortavoz
        emitir(EventoPortavoz(
            tipo="chalan.analisis_negocio",  # type: ignore[arg-type]
            actor_id=None, actor_email=None,
            payload={"dominio": dominio, "creadas": creadas},
        ))
    except Exception:  # noqa: BLE001
        logger.warning("emitir chalan.analisis_negocio falló", exc_info=True)
