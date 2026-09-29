"""El historial de actividad: qué pantallas abrió y qué guardó cada quien (2026-09-29).

La presencia (`lib.presencia`) contesta «¿dónde anda ahora?» y se sobrescribe.
Esto contesta «¿qué hizo el martes?», y se conserva un año. Las dos comparten el
mismo criterio de qué es una persona haciendo algo — **el sondeo no cuenta**
(`presencia.es_sondeo`) — y la misma forma de nombrar las pantallas
(`presencia._PANTALLAS`), así que lo que se lee en Equipo y lo que se lee aquí
nunca se contradicen.

Cuatro piezas:

1. **Registrar** (`registrar`, desde `cuentas.middleware.PresenciaMiddleware`).
   Un renglón por pantalla nueva y otro por cada acción que guarda algo (un POST
   que salió bien, también si redirige). NUNCA lanza. Para no repetir: la misma
   pantalla sólo se vuelve a anotar si la persona NAVEGA a ella otra vez y pasó un
   minuto (los fragmentos HTMX de la pantalla que ya tiene enfrente no cuentan);
   la misma acción repetida en menos de un minuto —un autoguardado— tampoco. El
   último renglón de cada tipo vive en la caché, así que el camino normal no
   consulta la base; si la caché no lo tiene, una sola consulta por índice.

2. **Quién hizo la petición** (`cabecera_quien`). El flujo de Peticiones en vivo
   se lee de los logs de gunicorn, que no saben de sesiones. El middleware pone
   `X-Despacho-Quien` en la respuesta, gunicorn la escribe en su línea de acceso,
   y El Portero la quita antes de que salga al navegador (`Caddyfile`, snippet
   `(sin_quien)`). Así cada renglón del flujo sabe de quién es sin escribir nada
   extra por petición.

3. **Mostrar** (`del_dia`). Igual que la presencia: se guardó lo crudo y el texto
   se arma aquí. El nombre de un registro sólo sale si quien mira podría abrirlo.

4. **Olvidar** (`purgar`). Un año y se borra — decisión de Oscar.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# Recargar la misma pantalla o repetir la misma acción antes de esto no repite renglón.
REPETIR_S = 60
# Un año (decisión de Oscar, 2026-09-29).
RETENCION_DIAS = 365
# Para sumar el tiempo activo de un día: un hueco mayor que esto no es estar
# trabajando. Es el mismo umbral que separa «en línea» de «ausente».
HUECO_ACTIVO_S = 5 * 60

CABECERA = "X-Despacho-Quien"

_LLAVE = "historial:ultimo:{uid}:{tipo}"


# ── 2 · Quién hizo la petición ───────────────────────────────────────────────


def _usuario_cargado(request):
    """El usuario de la petición SÓLO si ya se cargó.

    `request.user` es perezoso: evaluarlo cuesta la consulta de la sesión y la del
    usuario. Si la vista no lo necesitó (un recurso público), la cabecera no vale
    esas dos consultas.
    """
    from django.utils.functional import empty

    perezoso = request.__dict__.get("user")
    if perezoso is None:
        return None
    if getattr(perezoso, "_wrapped", None) is empty:
        return None
    return perezoso


def cabecera_quien(request) -> str:
    """`u:<id>` (el equipo), `u:<real>><como>` (impersonando) o `c:<acceso>` (un
    cliente del portal). Cadena vacía si la petición no trae a nadie."""
    try:
        usuario = _usuario_cargado(request)
        if usuario is not None and getattr(usuario, "is_authenticated", False) and usuario.pk:
            real = getattr(request, "impersonador", None)
            if real is not None and getattr(real, "pk", None) and real.pk != usuario.pk:
                return f"u:{real.pk}>{usuario.pk}"
            return f"u:{usuario.pk}"
        acceso = getattr(request, "acceso", None)
        if acceso is not None and getattr(acceso, "pk", None):
            return f"c:{acceso.pk}"
    except Exception:  # noqa: BLE001 — la cabecera es un extra; nunca tumba nada
        logger.debug("historial: no se pudo armar la cabecera", exc_info=True)
    return ""


def leer_quien(valor: str) -> dict | None:
    """El inverso de `cabecera_quien`: {'tipo': 'u'|'c', 'id': int, 'como': int|None}."""
    valor = (valor or "").strip()
    if len(valor) < 3 or valor[1] != ":" or valor[0] not in "uc":
        return None
    tipo, cuerpo = valor[0], valor[2:]
    real, _, como = cuerpo.partition(">")
    try:
        return {"tipo": tipo, "id": int(real), "como": int(como) if como else None}
    except ValueError:
        return None


# ── 1 · Registrar ────────────────────────────────────────────────────────────


def _cache():
    try:
        from django.core.cache import cache

        return cache
    except Exception:  # noqa: BLE001
        return None


def _ultimo(uid: int, tipo: str) -> tuple[str, float] | None:
    """(clave, marca epoch) del último renglón de ese tipo. Caché primero."""
    c = _cache()
    llave = _LLAVE.format(uid=uid, tipo=tipo)
    if c is not None:
        try:
            valor = c.get(llave)
            if valor:
                return tuple(valor)  # type: ignore[return-value]
        except Exception:  # noqa: BLE001 — Redis caído: se pregunta a la base
            pass
    from cuentas.models.registro_actividad import RegistroActividad

    fila = (
        RegistroActividad.objects.filter(usuario_id=uid, tipo=tipo)
        .order_by("-en").values_list("app", "ruta", "destino", "en").first()
    )
    if not fila:
        return None
    app, ruta, destino, en = fila
    return _clave(tipo, app, ruta, destino), en.timestamp()


def _recordar(uid: int, tipo: str, clave: str, marca: float) -> None:
    c = _cache()
    if c is None:
        return
    with contextlib.suppress(Exception):  # Redis caído: la próxima pregunta a la base
        c.set(_LLAVE.format(uid=uid, tipo=tipo), (clave, marca), REPETIR_S * 10)


def _clave(tipo: str, app: str, ruta: str, destino: str) -> str:
    return f"{app}|{destino if tipo == 'accion' else ruta}"


def _es_navegacion(request) -> bool:
    """¿La persona fue a esa pantalla (clic, enlace, recarga), o la pantalla pidió
    un pedazo de sí misma?"""
    headers = getattr(request, "headers", {}) or {}
    if headers.get("HX-Request") == "true":
        return headers.get("HX-Boosted") == "true"
    modo = (getattr(request, "META", {}) or {}).get("HTTP_SEC_FETCH_MODE", "")
    return not modo or modo == "navigate"


def _desde(request) -> str:
    """La pantalla desde la que se mandó una acción: la que la persona tenía
    enfrente, no el endpoint (que puede redirigir a otra parte)."""
    from lib import presencia

    headers = getattr(request, "headers", {}) or {}
    for url in (headers.get("HX-Current-URL", ""),
                (getattr(request, "META", {}) or {}).get("HTTP_REFERER", "")):
        ruta = presencia._mismo_sitio(url or "", request)
        if ruta:
            return ruta
    return getattr(request, "path", "") or "/"


def _ip(request) -> str:
    from lib.site.acciones import quien

    meta = getattr(request, "META", {}) or {}
    return quien(meta.get("HTTP_X_FORWARDED_FOR"), meta.get("REMOTE_ADDR"))[:64]


def _quienes(request):
    """(la persona que está ahí de verdad, a quién está mirando o None)."""
    usuario = getattr(request, "user", None)
    real = getattr(request, "impersonador", None)
    if real is not None and getattr(real, "pk", None):
        como = usuario if (usuario is not None and getattr(usuario, "pk", None) != real.pk) else None
        return real, como
    return usuario, None


def registrar(request, response) -> bool:
    """Anota una pantalla o una acción en el historial. NUNCA lanza."""
    try:
        return _registrar(request, response)
    except Exception:  # noqa: BLE001
        logger.debug("historial: no se pudo registrar", exc_info=True)
        return False


def _registrar(request, response) -> bool:
    from lib import presencia

    metodo = getattr(request, "method", "GET") or "GET"
    if metodo in ("HEAD", "OPTIONS"):
        return False
    estado = getattr(response, "status_code", 500)
    if estado >= 400:
        return False
    # Antes de tocar `request.user`, igual que la presencia: el sondeo ni siquiera
    # carga al usuario.
    if presencia.es_sondeo(request):
        return False
    usuario, como = _quienes(request)
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if not getattr(usuario, "is_active", True) or not getattr(usuario, "pk", None):
        return False

    from django.utils import timezone

    ahora = timezone.now()
    app = presencia.app_actual()

    if metodo == "GET":
        # Una redirección no es una pantalla: la anota la petición que sigue.
        if 300 <= estado < 400:
            return False
        tipo = "pantalla"
        ruta = presencia.ruta_de_pantalla(request, response)[:300]
        destino = ""
    else:
        # Una acción cuenta aunque redirija: guardar un formulario clásico SIEMPRE
        # redirige, y ése es justo el momento que importa.
        tipo = "accion"
        ruta = _desde(request)[:300]
        destino = (getattr(request, "path", "") or "")[:300]

    clave = _clave(tipo, app, ruta, destino)
    anterior = _ultimo(usuario.pk, tipo)
    if anterior and anterior[0] == clave:
        if tipo == "pantalla" and not _es_navegacion(request):
            return False
        if ahora.timestamp() - anterior[1] < REPETIR_S:
            return False

    url_name, kwargs = presencia._resolver(ruta)
    destino_url_name = presencia._resolver(destino)[0] if destino else ""
    from django.db import transaction

    from cuentas.models.registro_actividad import RegistroActividad

    with transaction.atomic():
        RegistroActividad.objects.create(
            usuario_id=usuario.pk,
            como_id=getattr(como, "pk", None),
            en=ahora, tipo=tipo, app=app,
            ruta=ruta, url_name=url_name, kwargs=kwargs,
            destino=destino, destino_url_name=destino_url_name,
            metodo=metodo[:8], ip=_ip(request), agente=presencia._agente(request),
        )
    _recordar(usuario.pk, tipo, clave, ahora.timestamp())
    return True


def marcar(request, user, tipo: str) -> None:
    """Entrar y cerrar sesión. NUNCA lanza."""
    try:
        if not user or not getattr(user, "pk", None):
            return
        from django.db import transaction
        from django.utils import timezone

        from cuentas.models.registro_actividad import RegistroActividad
        from lib import presencia

        with transaction.atomic():
            RegistroActividad.objects.create(
                usuario_id=user.pk, en=timezone.now(), tipo=tipo,
                app=presencia.app_actual(),
                ip=_ip(request) if request is not None else "",
                agente=presencia._agente(request) if request is not None else "",
            )
    except Exception:  # noqa: BLE001 — entrar o salir no puede fallar por esto
        logger.debug("historial: no se pudo marcar %s", tipo, exc_info=True)


# ── 3 · Mostrar ──────────────────────────────────────────────────────────────


def _regla(app: str, url_name: str):
    from lib import presencia

    return presencia._PANTALLAS_APP.get((app, url_name)) or presencia._PANTALLAS.get(url_name)


def _objeto(app: str, url_name: str, kwargs: dict, viewer, memo: dict) -> str:
    """Cómo se llama el registro de esa pantalla, o su genérico si quien mira no
    podría abrirlo. '' si la pantalla no es de un registro."""
    from lib import presencia

    regla = _regla(app, url_name)
    if not regla or not regla[2]:
        return ""
    tipo = regla[2]
    pk = (kwargs or {}).get("pk")
    llave = (tipo, str(pk))
    if llave not in memo:
        try:
            memo[llave] = presencia._objeto(tipo, pk, viewer)
        except Exception:  # noqa: BLE001
            memo[llave] = ("", False)
    texto, visible = memo[llave]
    return texto if (texto and visible) else presencia._GENERICO.get(tipo, "")


def _capital(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def describir(r, viewer=None, memo: dict | None = None, app_de_quien_mira: str = "") -> dict:
    """Un renglón del historial, listo para pintarse."""
    from django.utils import timezone

    from lib import presencia
    from lib.site.acciones import nombrar

    if memo is None:
        memo = {}
    detalle = ""
    url = ""
    if r.tipo == "entrada":
        texto = "Entró al sistema"
    elif r.tipo == "salida":
        texto = "Cerró sesión"
    elif r.tipo == "accion":
        objeto = _objeto(r.app, r.url_name, r.kwargs, viewer, memo)
        que = nombrar(r.destino) if r.destino else ""
        if objeto:
            texto = f"Guardó cambios en {objeto}"
            detalle = que
        else:
            base = presencia._seccion(r.app, r.ruta, r.url_name) or que
            texto = f"Guardó algo en {base}" if base else "Guardó algo"
            detalle = que if que != base else ""
    else:
        falso = SimpleNamespace(
            actividad_app=r.app, actividad_url_name=r.url_name,
            actividad_kwargs=r.kwargs, actividad_accion="ver", actividad_ruta=r.ruta,
        )
        pantalla, url = presencia._pantalla(falso, viewer, app_de_quien_mira, memo)
        texto = _capital(pantalla) or presencia._seccion(r.app, r.ruta, r.url_name) or r.ruta

    como = getattr(r, "como", None) if r.como_id else None
    return {
        "en": r.en,
        "hora": timezone.localtime(r.en).strftime("%H:%M:%S"),
        "tipo": r.tipo,
        "texto": texto,
        "detalle": detalle,
        "url": url,
        "app": r.app,
        "app_label": presencia.ETIQUETA_APP.get(r.app, ""),
        "ruta": r.ruta,
        "destino": r.destino,
        "ip": r.ip,
        "dispositivo": presencia.dispositivo(r.agente or ""),
        "como": (getattr(como, "nombre_completo", "") or getattr(como, "email", "")) if como else "",
    }


def limites_del_dia(fecha: date) -> tuple[datetime, datetime]:
    """[inicio, fin) del día en la hora del despacho (America/Mexico_City)."""
    from django.utils import timezone

    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(fecha, time.min), tz)
    return inicio, timezone.make_aware(datetime.combine(fecha + timedelta(days=1), time.min), tz)


def registros(persona, desde: datetime, hasta: datetime):
    from cuentas.models.registro_actividad import RegistroActividad

    return (
        RegistroActividad.objects.filter(usuario=persona, en__gte=desde, en__lt=hasta)
        .select_related("como")
    )


def resumen(filas: list) -> dict:
    """Primera y última vez, cuántas pantallas y acciones, y el tiempo activo.

    El tiempo activo suma los huecos entre renglones seguidos, cada uno topado en
    5 minutos: quien abre algo y se va a comer no suma la comida. Un hueco que
    empieza en «cerró sesión» no suma nada.
    """
    if not filas:
        return {"primera": None, "ultima": None, "pantallas": 0, "acciones": 0,
                "activo_min": 0, "activo_texto": ""}
    orden = sorted(filas, key=lambda r: r.en)
    segundos = 0.0
    for antes, despues in zip(orden, orden[1:], strict=False):
        if antes.tipo == "salida":
            continue
        segundos += min((despues.en - antes.en).total_seconds(), HUECO_ACTIVO_S)
    minutos = int(segundos // 60)
    horas, resto = divmod(minutos, 60)
    texto = (f"{horas} h {resto} min" if horas else f"{resto} min") if minutos else "menos de 1 min"
    return {
        "primera": orden[0].en,
        "ultima": orden[-1].en,
        "pantallas": sum(1 for r in orden if r.tipo == "pantalla"),
        "acciones": sum(1 for r in orden if r.tipo == "accion"),
        "activo_min": minutos,
        "activo_texto": texto,
    }


def del_dia(persona, fecha: date, viewer=None, app_de_quien_mira: str | None = None) -> dict:
    """Todo lo que se pinta de un día: el resumen y los renglones (lo último arriba)."""
    from lib import presencia

    if app_de_quien_mira is None:
        app_de_quien_mira = presencia.app_actual()
    desde, hasta = limites_del_dia(fecha)
    filas = list(registros(persona, desde, hasta).order_by("-en", "-pk"))
    memo: dict = {}
    return {
        "fecha": fecha,
        "resumen": resumen(filas),
        "items": [describir(r, viewer=viewer, memo=memo, app_de_quien_mira=app_de_quien_mira)
                  for r in filas],
    }


def dias_con_actividad(persona, hasta: date, n: int = 14) -> list[date]:
    """Los últimos días (hasta `hasta`, incluido) en que la persona hizo algo, para
    saltar de uno a otro sin adivinar fechas vacías."""
    from django.db.models.functions import TruncDate

    from cuentas.models.registro_actividad import RegistroActividad

    _, fin = limites_del_dia(hasta)
    return list(
        RegistroActividad.objects.filter(usuario=persona, en__lt=fin)
        .annotate(dia=TruncDate("en")).values_list("dia", flat=True)
        .distinct().order_by("-dia")[:n]
    )


CSV_COLUMNAS = ["fecha", "hora", "tipo", "app", "que", "detalle", "pantalla", "destino",
                "como", "ip", "aparato"]


def filas_csv(persona, desde: date, hasta: date, viewer=None) -> list[list[str]]:
    """Los renglones de [desde, hasta] (fechas incluidas), lo más viejo primero."""
    from django.utils import timezone

    inicio, _ = limites_del_dia(desde)
    _, fin = limites_del_dia(hasta)
    memo: dict = {}
    salida = []
    for r in registros(persona, inicio, fin).order_by("en", "pk").iterator(chunk_size=500):
        d = describir(r, viewer=viewer, memo=memo)
        local = timezone.localtime(r.en)
        salida.append([
            local.strftime("%Y-%m-%d"), local.strftime("%H:%M:%S"),
            dict(r.TIPOS).get(r.tipo, r.tipo), d["app_label"], d["texto"], d["detalle"],
            r.ruta, r.destino, d["como"], r.ip, d["dispositivo"]["texto"],
        ])
    return salida


def para_chalan(dia: dict) -> dict:
    """Lo que se le cuenta a El Chalán de un día — sin enlaces ni objetos."""
    res = dia["resumen"]

    def _h(dt):
        from django.utils import timezone

        return timezone.localtime(dt).strftime("%H:%M") if dt else ""

    return {
        "fecha": dia["fecha"].isoformat(),
        "primera_actividad": _h(res["primera"]),
        "ultima_actividad": _h(res["ultima"]),
        "tiempo_activo": res["activo_texto"] or "sin actividad",
        "pantallas": res["pantallas"],
        "acciones": res["acciones"],
        # Lo más viejo primero: así se lee como una bitácora.
        "linea_de_tiempo": [
            {"hora": i["hora"][:5], "app": i["app_label"], "que": i["texto"],
             **({"detalle": i["detalle"]} if i["detalle"] else {}),
             **({"como": i["como"]} if i["como"] else {})}
            for i in reversed(dia["items"][:80])
        ],
        "recortado": len(dia["items"]) > 80,
    }


# ── 4 · Olvidar ──────────────────────────────────────────────────────────────


def purgar(ahora=None, dias: int = RETENCION_DIAS, *, en_seco: bool = False) -> int:
    """Borra lo que tenga más de `dias`. Devuelve cuántos renglones (o cuántos
    borraría, en seco)."""
    from django.utils import timezone

    from cuentas.models.registro_actividad import RegistroActividad

    if ahora is None:
        ahora = timezone.now()
    viejos = RegistroActividad.objects.filter(en__lt=ahora - timedelta(days=dias))
    if en_seco:
        return viejos.count()
    total = 0
    # Por tandas: una sola sentencia sobre cientos de miles de renglones retiene
    # la tabla más de lo necesario.
    while True:
        pks = list(viejos.values_list("pk", flat=True)[:5000])
        if not pks:
            return total
        total += RegistroActividad.objects.filter(pk__in=pks).delete()[0]


__all__ = [
    "CABECERA", "CSV_COLUMNAS", "RETENCION_DIAS", "cabecera_quien", "del_dia",
    "dias_con_actividad", "filas_csv", "leer_quien", "marcar", "para_chalan",
    "purgar", "registrar", "resumen",
]
