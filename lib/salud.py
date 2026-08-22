"""El extremo `/salud` — lo único que El Despacho le contesta al monitor del taller.

El monitor **pregunta; nadie le reporta.** No hay agente que empuje datos ni puerto
nuevo abierto: pega un `GET /salud` a la dirección que ya sirve y lee este JSON.

## Los cuatro estados, y qué significa cada uno

| Estado | Cuándo | Qué hace el monitor |
|---|---|---|
| `ok` | funciona | nada |
| `degradado` | funciona **de menos** y hay algo que revisar | lo dice. **No abre alerta** |
| `apagado` | **a propósito** no está prendido | lo dice. **No abre alerta** |
| `falla` | está roto y hay que actuar | **cuenta como caída y despierta a alguien** |

**`falla` es la única palabra que despierta a alguien.** Se usa solo para lo que
justifica una notificación a media noche. Un módulo que se reporta `falla` porque
le falta una credencial opcional produce una alarma que nadie puede cerrar, y
cuatro de ésas entrenan a ignorar el tablero completo. **Si dudas entre
`degradado` y `falla`, es `degradado`.**

## Las tres reglas del extremo

1. **`Cache-Control: no-store`** (lo pone la vista). Un monitor cacheado miente en
   verde: un tablero sano con datos de ayer se ve idéntico a uno sano de verdad.
2. **Sin datos de negocio en la cara pública.** `/salud` lo puede leer cualquiera.
   Los conteos del negocio, los nombres de proveedores y cualquier cifra de dinero
   viven detrás de la cabecera `x-celador` (ver `lib/celador.py`).
3. **Un hueco no es un cero.** Si un dato no se pudo medir, se **omite la llave** o
   se manda `null`. Nunca `0`: un cero inventado se lee como «medido y está en
   ceros», que es lo contrario de «no se supo».

Nada aquí lanza. Cada módulo se mide en su propio `try` y, si no se puede medir, lo
dice en vez de tumbar la respuesta: un extremo de salud que devuelve 500 no informa,
solo agrega ruido.

**Sin memo a propósito.** Cada petición vuelve a medir (~15 consultas cortas y un
ping a Redis). Se consideró guardar el resultado unos segundos para que un flood no
cueste caro, y se descartó: la regla 1 del contrato es que el monitor no debe ver
datos viejos, y el costo por petición queda por debajo del de `/sign-in`, que
también es público y ahí sí se calcula un hash de contraseña. Si algún día hace
falta, el memo va aquí y NO en la cabecera HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# Umbrales — la cola del Portavoz crece cuando n8n no contesta; con esto pasa a
# `degradado` (hay algo que revisar) sin despertar a nadie.
UMBRAL_COLA_PENDIENTES = 200
# El respaldo corre cada 3 días (ver §10 del CLAUDE.md); 4 da un día de gracia.
DIAS_RESPALDO_TOLERADOS = 4

DIAS_VENTANA = 30


# ── Módulos de la cara pública ───────────────────────────────────────────────


def _m_base() -> dict[str, Any]:
    """Postgres: `SELECT 1`. Si no responde, la aplicación no sirve para nada."""
    from lib.site import postgres

    res = postgres.chequear()
    ms = res.get("latencia_ms")
    if res.get("estado") != "ok":
        return {
            "modulo": "base",
            "estado": "falla",
            "detalle": "la base de datos no responde",
        }
    # «0 ms» se lee como un hueco; es una medición real por debajo del milisegundo.
    det = "responde" if ms is None else ("<1 ms" if ms < 1 else f"{ms} ms")
    d = postgres.detalles()
    if d.get("disponible") and d.get("conexiones_activas") is not None:
        det += f" · {d['conexiones_activas']} conexiones"
    return {"modulo": "base", "estado": "ok", "detalle": det}


def _m_cola() -> dict[str, Any]:
    """Redis + la cola de El Portavoz. Redis caído tumba el rate-limit del login
    y deja los eventos sin encolar: eso sí es `falla`."""
    from lib.site import redis_status

    res = redis_status.chequear()
    if res.get("estado") != "ok":
        return {
            "modulo": "cola",
            "estado": "falla",
            # Sin Redis no hay conteo que dar: un hueco, no un cero.
            "detalle": "Redis no responde: sin cola de eventos ni límite de intentos de acceso",
        }
    d = redis_status.detalles()
    if not d.get("disponible"):
        return {"modulo": "cola", "estado": "degradado", "detalle": "responde pero no se pudo leer la cola"}
    pend = int(d.get("portavoz_cola") or 0)
    dlq = int(d.get("portavoz_dlq") or 0)
    det = f"{pend} pendientes"
    if dlq:
        det += f" · {dlq} descartados"
    if dlq or pend >= UMBRAL_COLA_PENDIENTES:
        return {"modulo": "cola", "estado": "degradado", "detalle": det}
    return {"modulo": "cola", "estado": "ok", "detalle": det}


def _m_correo() -> dict[str, Any]:
    """El Cartero. Sin canal configurado está **apagado a propósito**, no roto."""
    try:
        from lib import cartero

        if not cartero.esta_configurado():
            return {
                "modulo": "correo",
                "estado": "apagado",
                "detalle": "sin canal configurado: los avisos no salen",
            }
        return {"modulo": "correo", "estado": "ok", "detalle": f"canal {cartero.proveedor_activo()}"}
    except Exception:  # noqa: BLE001
        return {"modulo": "correo", "estado": "degradado", "detalle": "no se pudo determinar el canal"}


def _m_ia() -> dict[str, Any]:
    """Los Chalanes. Cuenta cuántos tienen llave; sin ninguno, la IA está apagada
    (el sistema entero sigue funcionando sin ella, así que nunca es `falla`)."""
    try:
        from lib.analistas.registry import _FACTORIES

        total = len(_FACTORIES)
        con_llave = 0
        for fabrica in _FACTORIES.values():
            try:
                if fabrica().esta_configurado():
                    con_llave += 1
            except Exception:  # noqa: BLE001 — un adapter roto no define la salud
                continue
    except Exception:  # noqa: BLE001
        return {"modulo": "ia", "estado": "degradado", "detalle": "no se pudo revisar a Los Chalanes"}
    if con_llave == 0:
        return {
            "modulo": "ia",
            "estado": "apagado",
            "detalle": "ningún Chalán tiene llave: el asistente no contesta",
        }
    return {"modulo": "ia", "estado": "ok", "detalle": f"{con_llave} de {total} Chalanes con llave"}


def _m_integraciones(de_la_casa: bool) -> dict[str, Any]:
    """Último chequeo de El Site por plataforma. Una integración externa caída no
    tumba el despacho — es `degradado`, no `falla`.

    Los NOMBRES de las plataformas solo salen con la credencial del Celador; en
    abierto va nada más el conteo.
    """
    from lib.salud_sistema import plataformas_en_error

    malas = plataformas_en_error()
    if not malas:
        return {"modulo": "integraciones", "estado": "ok", "detalle": "sin integraciones en rojo"}
    n = len(malas)
    det = f"{n} integración externa con problema" if n == 1 else f"{n} integraciones externas con problema"
    if de_la_casa:
        det += ": " + ", ".join(malas)
    return {"modulo": "integraciones", "estado": "degradado", "detalle": det}


def _a_datetime(valor: Any) -> datetime | None:
    """Normaliza lo que devuelva el cursor crudo: Postgres da `datetime`, SQLite
    da texto ISO. `None` si no se pudo interpretar."""
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=UTC)
    if isinstance(valor, str):
        try:
            d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return None
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    return None


def _ultimo_respaldo() -> dict[str, Any]:
    """El respaldo más reciente, mirando primero el registro del rsync a HAL y
    luego los archivos locales del Droplet. `{}` si no se pudo medir."""
    # SQL directo: la tabla vive en la base compartida, pero el modelo pertenece a
    # `apps.el_site`, que solo está instalada en La Gerencia (§14 Bug A).
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute(
                "SELECT archivo, destino, creado_en FROM site_backup_remoto "
                "WHERE estado = 'ok' ORDER BY creado_en DESC LIMIT 1"
            )
            fila = cur.fetchone()
        if fila:
            cuando = _a_datetime(fila[2])
            if cuando:
                return {"cuando": cuando, "archivo": fila[0], "destino": fila[1] or "remoto"}
    except Exception:  # noqa: BLE001 — tabla ausente o base sin responder
        pass
    try:
        from lib.site import internos

        local = internos.ultimo_backup_local()
        if local.get("disponible") and local.get("creado_en_ts"):
            return {
                "cuando": datetime.fromtimestamp(float(local["creado_en_ts"]), tz=UTC),
                "archivo": local.get("archivo") or "",
                "destino": "local",
            }
    except Exception:  # noqa: BLE001
        pass
    return {}


def _m_respaldo(de_la_casa: bool) -> dict[str, Any]:
    info = _ultimo_respaldo()
    if not info:
        return {
            "modulo": "respaldo",
            "estado": "degradado",
            # Un hueco, no un cero: NO se dice «0 días» ni «nunca».
            "detalle": "no se pudo determinar cuándo fue el último respaldo",
        }
    dias = max((datetime.now(tz=UTC) - info["cuando"]).days, 0)
    det = "de hoy" if dias == 0 else ("de ayer" if dias == 1 else f"hace {dias} días")
    if de_la_casa and info.get("archivo"):
        # El nombre del archivo lleva ruta/fecha: solo con credencial.
        det += f" · {info['archivo']} → {info['destino']}"
    estado = "degradado" if dias > DIAS_RESPALDO_TOLERADOS else "ok"
    return {"modulo": "respaldo", "estado": estado, "detalle": det}


def _m_memoria() -> dict[str, Any]:
    """¿Queda el colchón de memoria acordado en la máquina?

    Existe para que **nadie tenga que volver a un servidor headless a adivinar si
    le falta memoria**. El NUC quedó dimensionado (agosto 2026) para que la base y
    el catálogo crezcan cien veces sin tocar una cifra, con 4 G de colchón
    intocable. Este módulo es el que avisa el día en que ese colchón se empiece a
    comer: si nunca aparece en amarillo, no hay nada que ajustar.

    Se reporta **degradado**, no **falla**, cuando el colchón se estrecha: el
    sistema sigue funcionando y lo que hace falta es planear, no correr. Sólo
    cuando queda menos de la mitad pasa a falla — y ahí sí despierta a alguien,
    porque lo siguiente es que el kernel empiece a matar procesos.
    """
    from lib.site import host
    p = host.presion_memoria()
    if not p.get("disponible"):
        return {"modulo": "memoria", "estado": "apagado",
                "detalle": "no se puede leer /proc en este contenedor"}
    estado = {"ok": "ok", "aviso": "degradado", "falla": "falla"}[p["estado"]]
    return {"modulo": "memoria", "estado": estado, "detalle": p["detalle"]}


def modulos(de_la_casa: bool = False) -> list[dict[str, Any]]:
    """Los módulos de la cara pública, cada uno medido en su propio `try`."""
    medidas = (
        _m_base,
        _m_cola,
        _m_correo,
        _m_ia,
        _m_memoria,
        lambda: _m_integraciones(de_la_casa),
        lambda: _m_respaldo(de_la_casa),
    )
    salida: list[dict[str, Any]] = []
    for medir in medidas:
        try:
            salida.append(medir())
        except Exception:  # noqa: BLE001 — un módulo que no se puede medir lo dice
            continue
    return salida


def estado_del_conjunto(mods: list[dict[str, Any]]) -> str:
    """`falla` si algún módulo falla; si no, `degradado` si alguno lo está; si no,
    `ok`. Un módulo `apagado` a propósito NO degrada el conjunto.

    Si TODO está apagado (el caso de La Recepción hasta S5), el conjunto también
    es `apagado`: está así porque alguien lo decidió, no porque se rompiera.
    """
    estados = [m.get("estado", "ok") for m in mods]
    if "falla" in estados:
        return "falla"
    if "degradado" in estados:
        return "degradado"
    if estados and all(e == "apagado" for e in estados):
        return "apagado"
    return "ok"


# ── Nivel 2: el desglose con credencial ──────────────────────────────────────


def desglose_ia(dias: int = DIAS_VENTANA) -> dict[str, Any]:
    """Gasto de IA de la ventana. `costoMicro` en millonésimas de dólar, enteras,
    para no guardar flotantes de dinero.

    El contrato pide `null` cuando el costo no se puede calcular; aquí nunca es el
    caso: `AnalistaLog.costo_usd_estimado` no admite nulos y cada Chalán trae su
    tarifa, así que un `0` aquí es un cero **medido** (no hubo llamadas o no
    costaron), no un hueco. Si algún adapter dejara de imputar costo, éste es el
    lugar donde hay que devolver `None` en vez de sumar ceros.
    """
    from decimal import Decimal

    from lib.analistas.stats import estadisticas_proveedores

    stats = estadisticas_proveedores(dias=dias)
    llamadas = sum(int(d.get("llamadas") or 0) for d in stats.values())
    fallidas = sum(int(d.get("llamadas_falla") or 0) for d in stats.values())
    t_in = sum(int(d.get("prompt_tokens") or 0) for d in stats.values())
    t_out = sum(int(d.get("completion_tokens") or 0) for d in stats.values())
    costo = sum((Decimal(d.get("costo_usd") or 0) for d in stats.values()), Decimal("0"))
    return {
        "dias": dias,
        "llamadas": llamadas,
        "fallidas": fallidas,
        "tokensEntrada": t_in,
        "tokensSalida": t_out,
        "costoMicro": int((costo * 1_000_000).to_integral_value()),
    }


def desglose_uso(dias: int = DIAS_VENTANA) -> dict[str, Any]:
    """Quién está usando esto. `ingresos` cuenta **todos** los intentos de acceso
    que entraron; `fallidos`, los que no — los dos por separado, porque un día con
    treinta fallidos y dos entradas significa algo muy distinto de treinta entradas.

    Mientras la bitácora de accesos esté vacía, `ingresos`/`fallidos` van en `null`:
    un `0` ahí se leería como «nadie entró» cuando la verdad es «todavía no se está
    midiendo». `registrandoDesde` dice desde cuándo hay datos.
    """
    from django.db.models import Q
    from django.utils import timezone

    from cuentas.models.intento_acceso import IntentoAcceso
    from cuentas.models.usuario import Usuario

    desde = timezone.now() - timedelta(days=dias)
    out: dict[str, Any] = {"dias": dias, "ingresos": None, "fallidos": None, "cuentasActivas": None}

    primero = IntentoAcceso.objects.order_by("creado_en").values_list("creado_en", flat=True).first()
    if primero is not None:
        qs = IntentoAcceso.objects.filter(creado_en__gte=desde)
        out["ingresos"] = qs.count()
        out["fallidos"] = qs.filter(exito=False).count()
        out["registrandoDesde"] = primero.isoformat()

    # Cuentas activas sale de `ultimo_acceso_en`, que se lleva desde S1a: es un dato
    # medido de verdad, incluso el primer día de la bitácora.
    out["cuentasActivas"] = Usuario.objects.filter(
        Q(is_active=True) & Q(ultimo_acceso_en__gte=desde)
    ).count()
    return out


# ── Armado de la respuesta ───────────────────────────────────────────────────


def payload(*, app: str, de_la_casa: bool = False, dias: int = DIAS_VENTANA) -> tuple[dict[str, Any], int]:
    """Devuelve `(cuerpo, codigo_http)`.

    El código acompaña al estado: `200` para `ok`/`degradado`/`apagado` y `503`
    **solo** para `falla`. El monitor lee el JSON, no el código; el código es para
    cualquier otra cosa que mire este extremo (un balanceador, un healthcheck de
    Docker).
    """
    from lib.version import VERSION

    mods = modulos(de_la_casa=de_la_casa)
    estado = estado_del_conjunto(mods)
    cuerpo: dict[str, Any] = {
        "estado": estado,
        "version": VERSION,
        "app": app,
        "modulos": mods,
    }
    if de_la_casa:
        for clave, fn in (("ia", desglose_ia), ("uso", desglose_uso)):
            try:
                cuerpo[clave] = fn(dias)
            except Exception:  # noqa: BLE001 — omitir la llave es honesto; un cero no
                continue
    return cuerpo, (503 if estado == "falla" else 200)


__all__ = [
    "DIAS_RESPALDO_TOLERADOS",
    "DIAS_VENTANA",
    "UMBRAL_COLA_PENDIENTES",
    "desglose_ia",
    "desglose_uso",
    "estado_del_conjunto",
    "modulos",
    "payload",
]
