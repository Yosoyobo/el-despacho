"""La presencia: quién está en línea y en qué pantalla anda cada quien.

Sprint de pendientes 2026-09-28. Decisiones de Oscar, literales:

- **Dónde**: El Directorio (La Gerencia), El Site y El Vigía (a la par, §4 #22),
  Equipo y el Dashboard (El Taller).
- **«En línea»** = actividad en los últimos 5 minutos; de 5 a 30 = **ausente**;
  más = **desconectado**, con la hora.
- **Detalle**: hora + sección + app + pantalla exacta + dispositivo.
- **Quién ve**: todos — con el permiso granular `(equipo, ver_actividad)`, que
  nace activo para todos y se revoca por usuario (§4 #20).

Tres piezas, y en este orden importan:

1. **Registrar** (`registrar`, lo llama `cuentas.middleware.PresenciaMiddleware`
   al terminar cada petición). NUNCA lanza y NUNCA escribe en cada petición: el
   usuario ya viene cargado de la base (lo carga el middleware de autenticación),
   así que el tope se decide con SUS campos, sin una consulta extra y sin
   depender de Redis. Se escribe a lo más **una vez por minuto si sigue en la
   misma pantalla**, y **una cada 15 s si cambió de pantalla** — el segundo tope
   existe porque la «pantalla exacta» es parte de lo que se pidió: con un minuto
   parejo, quien salta de un proyecto a una cotización seguiría apareciendo en el
   proyecto hasta un minuto después.

2. **No contar el sondeo.** La actividad la marca una PERSONA, no la pestaña: el
   banner de deploy y el semáforo (cada 10 s), las bandejas de Mensajes (cada 5 y
   15 s), los paneles de El Vigía / El Site y este mismo recuadro se piden solos.
   Si contaran, todo el mundo saldría «en línea» con la pestaña abierta — que es
   justo lo que Oscar descartó. La lista vive en `URL_NAMES_SONDEO` y
   `tests/test_presencia_sep28.py` exige que TODO elemento con
   `hx-trigger="every …"` esté ahí: el siguiente que agregue un sondeo y no lo
   registre rompe el build en vez de romper la pantalla en silencio.

3. **Mostrar** (`describir` / `equipo_ahora`). Se guarda lo CRUDO (ruta, nombre de
   la URL, sus argumentos) y el texto legible se arma aquí, al mostrarlo. Así la
   escritura no consulta nada, y un proyecto renombrado se lee con su nombre de
   hoy. **El nombre del objeto sólo sale si quien mira también podría abrirlo**:
   todos ven que Jorge está «editando una factura», pero sólo quien entra a
   Facturación ve «editando la factura F108». Mostrar a todos quién está y en qué
   sección es lo que se decidió; filtrar el NOMBRE de lo que no puedes abrir es lo
   que impide que la presencia se vuelva una ventana a módulos ajenos.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import timedelta
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# ── Los umbrales (decisión de Oscar) ─────────────────────────────────────────

EN_LINEA_S = 5 * 60
AUSENTE_S = 30 * 60

# ── El tope de escritura ─────────────────────────────────────────────────────

TOPE_MISMA_PANTALLA_S = 60
TOPE_CAMBIO_PANTALLA_S = 15

# Marcas especiales en `actividad_url_name` para lo que no es una pantalla.
ENTRADA = "__entrada__"
SALIDA = "__salida__"

# ── El sondeo automático ─────────────────────────────────────────────────────
#
# Lo que las pantallas piden SOLAS. Nada de esto es una persona haciendo algo.
# Si agregas un `hx-trigger="every …"` nuevo, su url_name va aquí — el test lo
# exige.
URL_NAMES_SONDEO = frozenset({
    # El banner de deploy y el semáforo del header (cada 10 s, las dos apps).
    "aviso-deploy",
    "aviso-deploy-semaforo",
    # Mensajes: la bandeja (cada 15 s) y los mensajes nuevos (cada 5 s).
    "recados:partial_bandeja",
    "recados:partial_mensajes",
    # Los que responden a monitores y al navegador, no a personas.
    "salud",
    "taller-ping",
    "gerencia-ping",
    "interfono-sw",
    "interfono-offline",
    # La cola offline de El Checador se vacía sola al recuperar la señal.
    "checador:api_sync",
    # Este mismo sistema: el recuadro «Quién está conectado» se refresca solo.
    "directorio-en-linea",
})

# Los paneles de El Vigía / El Site se nombran todos `site-vivo-*`; se cubren
# por prefijo para que un panel nuevo no tenga que acordarse de esta lista.
PREFIJO_NOMBRE_SONDEO = "site-vivo"

PREFIJOS_RUTA_SONDEO = (
    "/static/",
    "/medios/",
    "/salud",
    "/ping",
    "/sw.js",
    "/offline/",
    "/manifest",
    "/favicon",
    "/sistema/",
    "/site/vivo",
)

# Para un sondeo futuro que no quiera registrarse en la lista: basta con
# `hx-headers='{"X-Despacho-Sondeo": "1"}'` en el elemento.
CABECERA_SONDEO = "HTTP_X_DESPACHO_SONDEO"

# ── Cómo se llama cada cosa en pantalla ──────────────────────────────────────

ETIQUETA_APP = {
    "taller": "El Taller",
    "gerencia": "La Gerencia",
    "recepcion": "La Recepción",
}

ESTADOS = {
    "en_linea": {"label": "En línea", "orden": 0},
    "ausente": {"label": "Ausente", "orden": 1},
    "desconectado": {"label": "Desconectado", "orden": 2},
    "nunca": {"label": "Sin actividad registrada", "orden": 3},
}

# Secciones que cambian de nombre según la app. `lib.site.acciones.nombrar` las
# nombra sin saber de qué app vienen, y en El Taller `/directorio/` es Equipo
# mientras que en La Gerencia es El Directorio.
_SECCIONES_APP = {
    "taller": (
        ("/directorio/", "Equipo"),
    ),
    "gerencia": (
        ("/directorio/", "El Directorio"),
        ("/ajustes/", "Los Ajustes"),
        ("/catalogos/", "Catálogos"),
        ("/interfono/", "El Interfón"),
        ("/checador/", "Horarios y correcciones"),
        ("/site/", "El Site"),
        ("/chalanes/", "Los Chalanes"),
    ),
}

# La pantalla exacta. `url_name` → (texto si mira, texto si edita, tipo de objeto).
# Con tipo, el texto es el verbo y el objeto se nombra detrás («editando
# LC-0044 · Gorras Cruz Azul»). Sin tipo, el texto va solo.
_PANTALLAS = {
    "taller-home": ("en el Dashboard", "en el Dashboard", None),
    "gerencia-home": ("en el inicio de La Gerencia", "en el inicio de La Gerencia", None),
    "proyectos-kanban": ("en el tablero de proyectos", "moviendo el tablero de proyectos", None),
    "proyectos-lista": ("en la lista de proyectos", "en la lista de proyectos", None),
    "proyectos-nuevo": ("dando de alta un proyecto", "dando de alta un proyecto", None),
    "proyectos-cancelaciones": ("en las cancelaciones", "en las cancelaciones", None),
    "proyectos-detalle": ("viendo", "editando", "proyecto"),
    "proyectos-editar": ("editando", "editando", "proyecto"),
    "cotizaciones:lista": ("en Cotizaciones", "en Cotizaciones", None),
    "cotizaciones:nuevo": ("armando una cotización", "armando una cotización", None),
    "cotizaciones:detalle": ("viendo", "editando", "cotizacion"),
    "cotizaciones:editar": ("editando", "editando", "cotizacion"),
    "facturacion:lista": ("en Facturación", "en Facturación", None),
    "facturacion:nueva": ("capturando una factura", "capturando una factura", None),
    "facturacion:detalle": ("viendo", "editando", "factura"),
    "facturacion:editar": ("editando", "editando", "factura"),
    "cartera-lista": ("en Clientes", "en Clientes", None),
    "cartera-nuevo": ("dando de alta un cliente", "dando de alta un cliente", None),
    "cartera-detalle": ("viendo", "editando", "cliente"),
    "cartera-editar": ("editando", "editando", "cliente"),
    "catalogo-lista": ("en Productos", "en Productos", None),
    "catalogo-nuevo": ("dando de alta un producto", "dando de alta un producto", None),
    "catalogo-editar": ("viendo", "editando", "producto"),
    "catalogo-usos": ("viendo los usos de", "viendo los usos de", "producto"),
    "catalogo-proveedores": ("en Proveedores", "en Proveedores", None),
    "catalogo-proveedor-nuevo": ("dando de alta un proveedor", "dando de alta un proveedor", None),
    "catalogo-proveedor-detalle": ("viendo", "editando", "proveedor"),
    "catalogo-proveedor-editar": ("editando", "editando", "proveedor"),
    "tareas-kanban": ("en el tablero de tareas", "moviendo el tablero de tareas", None),
    "tareas-lista": ("en la lista de tareas", "en la lista de tareas", None),
    "pizarron-nueva-tarea-global": ("dando de alta una tarea", "dando de alta una tarea", None),
    "pizarron-detalle-tarea": ("viendo", "editando", "tarea"),
    "pizarron-editar-tarea": ("editando", "editando", "tarea"),
    "mandados-lista": ("en Mandados", "en Mandados", None),
    "mandados-mi-ruta": ("en su ruta del día", "en su ruta del día", None),
    "rutas-panel": ("en el planeador de rutas", "armando las rutas", None),
    "calendario-index": ("en el Calendario", "en el Calendario", None),
    "chalan-chat": ("platicando con El Chalán", "platicando con El Chalán", None),
    "chalan-conversacion": ("platicando con El Chalán", "platicando con El Chalán", None),
    "recados:bandeja": ("en Mensajes", "escribiendo en Mensajes", None),
    "recados:conversacion": ("en una conversación de Mensajes", "escribiendo en Mensajes", None),
    "recados:zona_buzon": ("en Mi Buzón", "en Mi Buzón", None),
    "tesoreria:landing": ("en Tesorería", "en Tesorería", None),
    "tesoreria:ingresos-lista": ("en los ingresos", "en los ingresos", None),
    "tesoreria:egresos-lista": ("en los egresos", "en los egresos", None),
    "tesoreria:ingreso-detalle": ("viendo", "editando", "ingreso"),
    "tesoreria:ingreso-editar": ("editando", "editando", "ingreso"),
    "tesoreria:egreso-detalle": ("viendo", "editando", "egreso"),
    "tesoreria:egreso-editar": ("editando", "editando", "egreso"),
    "papeleo-buscar": ("en el Papeleo", "en el Papeleo", None),
    "taller-analisis": ("en El Análisis", "en El Análisis", None),
    "ayuda": ("leyendo el manual", "leyendo el manual", None),
}

# El mismo nombre de URL en las dos apps significa cosas distintas: aquí manda
# la app. Se consulta ANTES que `_PANTALLAS`.
_PANTALLAS_APP = {
    ("taller", "directorio-lista"): ("en Equipo", "en Equipo", None),
    ("taller", "directorio-perfil"): ("viendo la ficha de", "viendo la ficha de", "persona"),
    ("gerencia", "directorio-lista"): ("en El Directorio", "en El Directorio", None),
    ("gerencia", "site-tablero"): ("en El Site", "en El Site", None),
}

# Lo que se dice cuando quien mira NO podría abrir el objeto (o ya no existe).
_GENERICO = {
    "proyecto": "un proyecto",
    "cotizacion": "una cotización",
    "factura": "una factura",
    "cliente": "un cliente",
    "producto": "un producto",
    "proveedor": "un proveedor",
    "tarea": "una tarea",
    "persona": "una ficha del equipo",
    "ingreso": "un ingreso",
    "egreso": "un egreso",
}


# ── La app y la pantalla de una petición ─────────────────────────────────────


def app_actual() -> str:
    """De qué app viene la petición: taller, gerencia o recepcion.

    Se deduce del urlconf (las tres comparten base de datos, así que la fila del
    usuario no lo sabe). `DESPACHO_APP` en settings manda si alguien lo pone.
    """
    try:
        from django.conf import settings
        from django.urls import get_urlconf

        explicito = getattr(settings, "DESPACHO_APP", "")
        if explicito:
            return str(explicito)
        urlconf = get_urlconf() or getattr(settings, "ROOT_URLCONF", "") or ""
        urlconf = str(getattr(urlconf, "__name__", urlconf))
        for clave in ("gerencia", "taller", "recepcion"):
            if clave in urlconf:
                return clave
    except Exception:  # noqa: BLE001
        pass
    return ""


def es_sondeo(request) -> bool:
    """¿La pidió la pantalla sola? Si sí, no es actividad de una persona."""
    ruta = getattr(request, "path", "") or ""
    if ruta.startswith(PREFIJOS_RUTA_SONDEO):
        return True
    meta = getattr(request, "META", {}) or {}
    if meta.get(CABECERA_SONDEO):
        return True
    match = getattr(request, "resolver_match", None)
    nombre = getattr(match, "view_name", "") or ""
    return nombre in URL_NAMES_SONDEO or nombre.startswith(PREFIJO_NOMBRE_SONDEO)


def _mismo_sitio(url: str, request) -> str:
    """La ruta de `url` si es de este mismo sitio (o relativa); '' si no.

    Un encabezado lo manda el navegador y se puede falsificar, pero aquí sólo
    decide qué pantalla se le ANOTA a quien ya está autenticado: lo peor que
    alguien lograría es mentir sobre dónde anda él mismo.
    """
    if not url:
        return ""
    try:
        partes = urlsplit(url)
    except ValueError:
        return ""
    if partes.netloc:
        try:
            host = request.get_host()
        except Exception:  # noqa: BLE001
            host = ""
        if partes.netloc.lower() != (host or "").lower():
            return ""
    ruta = partes.path or ""
    return ruta if ruta.startswith("/") else ""


def ruta_de_pantalla(request, response=None) -> str:
    """La pantalla que la persona TIENE ENFRENTE, no el fragmento que se pidió.

    - HTMX manda `HX-Current-URL`: un modal o un autoguardado se piden a su propio
      endpoint, pero la persona sigue viendo el proyecto. Si la respuesta la manda
      a otra página (`HX-Redirect`), ésa es la pantalla nueva.
    - Un formulario clásico que redirige: la pantalla es a donde lo mandan.
    - Un `fetch` de fondo (el navegador lo marca con `Sec-Fetch-Mode` distinto de
      `navigate`): la pantalla es la que lo pidió (`Referer`).
    - Lo demás es una navegación: la pantalla es la ruta misma.
    """
    headers = getattr(request, "headers", {}) or {}
    meta = getattr(request, "META", {}) or {}
    status = getattr(response, "status_code", 200) if response is not None else 200

    if headers.get("HX-Request") == "true":
        if response is not None:
            destino = _mismo_sitio(response.get("HX-Redirect", "") or "", request)
            if destino:
                return destino
        actual = _mismo_sitio(headers.get("HX-Current-URL", "") or "", request)
        if actual:
            return actual
    elif 300 <= status < 400 and response is not None:
        destino = _mismo_sitio(response.get("Location", "") or "", request)
        if destino:
            return destino
    else:
        modo = meta.get("HTTP_SEC_FETCH_MODE", "")
        if modo and modo != "navigate":
            origen = _mismo_sitio(meta.get("HTTP_REFERER", ""), request)
            if origen:
                return origen
    return getattr(request, "path", "") or "/"


def _resolver(ruta: str) -> tuple[str, dict]:
    """(url_name con namespace, kwargs simples) de una ruta; ('', {}) si no casa."""
    try:
        from django.urls import resolve

        match = resolve(ruta)
    except Exception:  # noqa: BLE001 — Resolver404 incluido
        return "", {}
    kwargs = {
        k: v for k, v in (match.kwargs or {}).items()
        if isinstance(v, int | str) and len(str(v)) <= 60
    }
    return (match.view_name or "")[:120], kwargs


def _agente(request) -> str:
    try:
        return (request.META.get("HTTP_USER_AGENT") or "")[:300]
    except Exception:  # noqa: BLE001
        return ""


# ── Registrar ────────────────────────────────────────────────────────────────


def toca_escribir(usuario, ruta: str, app: str, accion: str, ahora) -> bool:
    """¿Toca escribir? Con los campos que el usuario YA trae cargados — sin
    consultar nada.

    Una vez por minuto si sigue en la misma pantalla haciendo lo mismo; una cada
    15 s si cambió de pantalla (o pasó de mirar a editar). Así «en línea» nunca se
    atrasa más de un minuto y la pantalla exacta no se queda pegada a la anterior.
    """
    ultima = getattr(usuario, "actividad_en", None)
    if ultima is None:
        return True
    transcurrido = (ahora - ultima).total_seconds()
    if transcurrido < 0:
        # Un reloj adelantado no puede dejar a alguien congelado: se trata como
        # si acabara de escribirse, y el tope corre desde aquí.
        transcurrido = 0
    marca = getattr(usuario, "actividad_url_name", "") or ""
    misma = (
        marca not in (ENTRADA, SALIDA)
        and (getattr(usuario, "actividad_ruta", "") or "") == ruta
        and (getattr(usuario, "actividad_app", "") or "") == app
        and (getattr(usuario, "actividad_accion", "") or "") == accion
    )
    tope = TOPE_MISMA_PANTALLA_S if misma else TOPE_CAMBIO_PANTALLA_S
    return transcurrido >= tope


def _guardar(usuario, campos: dict) -> bool:
    """Escribe la actividad con un UPDATE directo, dentro de su propio punto de
    guardado.

    `update()` y no `save()`: no dispara signals ni toca `actualizado_en` (que
    dice cuándo se editó la ficha, no cuándo se usó el sistema). Y el `atomic`
    no es adorno: si esta escritura falla, el punto de guardado se revierte solo
    y la transacción de la petición —si la hubiera— sigue sana.
    """
    from django.db import transaction

    from cuentas.models.usuario import Usuario

    with transaction.atomic():
        Usuario.objects.filter(pk=usuario.pk).update(**campos)
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    return True


def registrar(request, response) -> bool:
    """Anota la actividad de quien hizo la petición. NUNCA lanza.

    Devuelve True si escribió. La presencia no puede ser el motivo de que una
    pantalla falle: cualquier error se traga y se deja en el log.
    """
    try:
        return _registrar(request, response)
    except Exception:  # noqa: BLE001
        logger.debug("presencia: no se pudo registrar la actividad", exc_info=True)
        return False


def _registrar(request, response) -> bool:
    if getattr(request, "method", "GET") in ("HEAD", "OPTIONS"):
        return False
    if getattr(response, "status_code", 500) >= 400:
        return False
    # El sondeo se descarta ANTES de tocar `request.user`: así una petición
    # automática ni siquiera carga al usuario si la vista no lo hizo.
    if es_sondeo(request):
        return False
    # Durante una impersonación, `request.user` es la persona impersonada. La
    # actividad es del super_admin que está ahí de verdad, no de quien él mira.
    usuario = getattr(request, "impersonador", None) or getattr(request, "user", None)
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return False
    if not getattr(usuario, "is_active", True) or not getattr(usuario, "pk", None):
        return False

    from django.utils import timezone

    ahora = timezone.now()
    ruta = ruta_de_pantalla(request, response)[:300]
    app = app_actual()
    accion = "ver" if request.method == "GET" else "editar"
    if not toca_escribir(usuario, ruta, app, accion, ahora):
        return False

    url_name, kwargs = _resolver(ruta)
    return _guardar(usuario, {
        "actividad_en": ahora,
        "actividad_app": app,
        "actividad_ruta": ruta,
        "actividad_url_name": url_name,
        "actividad_kwargs": kwargs,
        "actividad_accion": accion,
        "actividad_agente": _agente(request),
    })


def _marcar(request, user, marca: str) -> None:
    try:
        if not user or not getattr(user, "pk", None):
            return
        from django.utils import timezone

        _guardar(user, {
            "actividad_en": timezone.now(),
            "actividad_app": app_actual(),
            "actividad_ruta": "",
            "actividad_url_name": marca,
            "actividad_kwargs": {},
            "actividad_accion": "",
            "actividad_agente": _agente(request) if request is not None else "",
        })
    except Exception:  # noqa: BLE001 — entrar o salir no puede fallar por esto
        logger.debug("presencia: no se pudo marcar %s", marca, exc_info=True)


def marcar_entrada(request, user) -> None:
    """Entrar al sistema ya es estar aquí."""
    _marcar(request, user, ENTRADA)


def marcar_salida(request, user) -> None:
    """Cerrar sesión es la única forma de saber que alguien se fue ANTES de los
    30 minutos. Sin esto, quien sale aparecería «en línea» cinco minutos más."""
    _marcar(request, user, SALIDA)


# ── Mostrar ──────────────────────────────────────────────────────────────────


def estado_de(usuario, ahora=None) -> str:
    """en_linea · ausente · desconectado · nunca."""
    ultima = getattr(usuario, "actividad_en", None)
    if ultima is None:
        return "nunca"
    if (getattr(usuario, "actividad_url_name", "") or "") == SALIDA:
        return "desconectado"
    if ahora is None:
        from django.utils import timezone

        ahora = timezone.now()
    segundos = max(0.0, (ahora - ultima).total_seconds())
    if segundos <= EN_LINEA_S:
        return "en_linea"
    if segundos <= AUSENTE_S:
        return "ausente"
    return "desconectado"


def _hora(dt) -> str:
    """La hora local, respetando la preferencia 24h / AM-PM de quien mira."""
    from django.utils import timezone
    from django.utils.dateformat import format as formatear

    from lib.formato_hora import aplicar

    return formatear(timezone.localtime(dt), aplicar("H:i"))


def hace(dt, ahora=None) -> str:
    """«hace un momento» · «hace 12 min» · «hoy a las 14:03» · «ayer a las
    18:10» · «22/09 a las 11:20»."""
    if dt is None:
        return ""
    from django.utils import timezone

    if ahora is None:
        ahora = timezone.now()
    segundos = max(0.0, (ahora - dt).total_seconds())
    if segundos < 60:
        return "hace un momento"
    if segundos < 60 * 60:
        return f"hace {int(segundos // 60)} min"
    dia = timezone.localtime(dt).date()
    hoy = timezone.localtime(ahora).date()
    if dia == hoy:
        return f"hoy a las {_hora(dt)}"
    if dia == hoy - timedelta(days=1):
        return f"ayer a las {_hora(dt)}"
    return f"{dia.strftime('%d/%m')} a las {_hora(dt)}"


def dispositivo(agente: str) -> dict:
    """Computadora / celular / tableta, sistema y navegador, leídos del
    User-Agent. Sin librería: para cinco personas basta con reconocer lo común.

    El orden importa: Edge y Opera se anuncian también como Chrome, Chrome en el
    iPhone dice «CriOS» y Safari aparece en la cadena de casi todos.
    """
    crudo = agente or ""
    b = crudo.lower()
    if not b:
        return {"tipo": "", "so": "", "navegador": "", "texto": "", "icono": ""}
    if any(x in b for x in ("curl/", "wget/", "python", "httpx", "bot", "spider")):
        return {"tipo": "guion", "so": "", "navegador": "", "texto": "Un guion",
                "icono": "⚙️"}

    if "ipad" in b:
        so, tipo = "iPadOS", "tableta"
    elif "iphone" in b or "ipod" in b:
        so, tipo = "iOS", "celular"
    elif "android" in b:
        so, tipo = "Android", ("celular" if "mobile" in b else "tableta")
    elif "windows" in b:
        so, tipo = "Windows", "computadora"
    elif "cros" in b:
        so, tipo = "ChromeOS", "computadora"
    elif "macintosh" in b or "mac os x" in b:
        so, tipo = "macOS", "computadora"
    elif "linux" in b:
        so, tipo = "Linux", "computadora"
    else:
        so, tipo = "", ("celular" if "mobile" in b else "computadora")

    if "edg/" in b or "edga/" in b or "edgios/" in b:
        navegador = "Edge"
    elif "opr/" in b or "opera" in b:
        navegador = "Opera"
    elif "samsungbrowser" in b:
        navegador = "Samsung Internet"
    elif "crios" in b:
        navegador = "Chrome"
    elif "fxios" in b or "firefox" in b:
        navegador = "Firefox"
    elif "chrome" in b or "chromium" in b:
        navegador = "Chrome"
    elif "safari" in b:
        navegador = "Safari"
    else:
        navegador = ""

    partes = [tipo.capitalize()] + [p for p in (so, navegador) if p]
    return {
        "tipo": tipo,
        "so": so,
        "navegador": navegador,
        "texto": " · ".join(partes),
        "icono": "💻" if tipo == "computadora" else "📱",
    }


def _seccion(app: str, ruta: str, url_name: str) -> str:
    if url_name == ENTRADA:
        return "Entró al sistema"
    if url_name == SALIDA:
        return "Cerró sesión"
    if not ruta:
        return ""
    if app == "gerencia" and ruta == "/":
        return "Inicio de La Gerencia"
    for prefijo, nombre in _SECCIONES_APP.get(app, ()):
        if ruta.startswith(prefijo):
            return nombre
    try:
        from lib.site.acciones import nombrar

        return nombrar(ruta)
    except Exception:  # noqa: BLE001
        return ruta


def _modelo(app_label: str, nombre: str):
    try:
        from django.apps import apps

        return apps.get_model(app_label, nombre)
    except Exception:  # noqa: BLE001 — la app no está instalada en este proyecto
        return None


def _objeto(tipo: str, pk, viewer) -> tuple[str, bool]:
    """(cómo se llama, ¿quien mira podría abrirlo?). ('', False) si no existe.

    `viewer=None` es la pared de El Vigía: una pantalla en la oficina, que ya
    enseña el flujo de peticiones con quién y a dónde. Ahí se ve todo.
    """
    from lib import permisos

    def _puede(fn) -> bool:
        if viewer is None:
            return True
        try:
            return bool(fn())
        except Exception:  # noqa: BLE001
            return False

    if pk in (None, ""):
        return "", False

    if tipo == "proyecto":
        Proyecto = _modelo("proyectos", "Proyecto")
        p = Proyecto and Proyecto.objects.filter(pk=pk).first()
        if not p:
            return "", False
        return f"{p.codigo} · {p.nombre}", _puede(lambda: permisos.puede_ver_proyecto(viewer, p))

    if tipo == "cotizacion":
        Cotizacion = _modelo("cotizaciones", "Cotizacion")
        c = Cotizacion and Cotizacion.objects.select_related("proyecto").filter(pk=pk).first()
        if not c:
            return "", False
        texto = f"la cotización {c.codigo}"
        if getattr(c, "version", 0):
            texto += f" v{c.version}"
        if getattr(c, "proyecto", None):
            texto += f" · {c.proyecto.nombre}"
        return texto, _puede(lambda: permisos.puede_ver_cotizaciones(viewer))

    if tipo == "factura":
        Factura = _modelo("facturacion", "Factura")
        f = Factura and Factura.objects.filter(pk=pk).first()
        if not f:
            return "", False
        return (f"la factura {getattr(f, 'folio', '') or f.codigo}",
                _puede(lambda: permisos.puede_ver_facturacion(viewer)))

    if tipo == "cliente":
        Cliente = _modelo("cartera", "Cliente")
        c = Cliente and Cliente.objects.filter(pk=pk).first()
        if not c:
            return "", False
        return c.razon_social, _puede(lambda: permisos.puede_ver_cartera(viewer))

    if tipo in ("producto", "proveedor"):
        Modelo = _modelo("el_catalogo", "Servicio" if tipo == "producto" else "Proveedor")
        o = Modelo and Modelo.objects.filter(pk=pk).first()
        if not o:
            return "", False
        nombre = o.nombre if tipo == "producto" else o.razon_social
        articulo = "el producto" if tipo == "producto" else "el proveedor"
        return (f"{articulo} {nombre}",
                _puede(lambda: permisos.puede(viewer, "catalogo", "ver_nombres")))

    if tipo == "tarea":
        Tarea = _modelo("pizarron", "Tarea")
        t = Tarea and Tarea.objects.select_related("proyecto").filter(pk=pk).first()
        if not t:
            return "", False
        if t.proyecto_id is None:
            visible = True
        else:
            visible = _puede(lambda: permisos.puede_ver_tarea(viewer, t))
        return f"la tarea «{t.titulo}»", visible

    if tipo == "persona":
        from cuentas.models.usuario import Usuario

        u = Usuario.objects.filter(pk=pk).first()
        if not u:
            return "", False
        # Equipo lo ve todo el despacho, así que la ficha de alguien no es secreta.
        return u.nombre_completo or u.email, True

    if tipo in ("ingreso", "egreso"):
        Modelo = _modelo("tesoreria", "Ingreso" if tipo == "ingreso" else "Egreso")
        o = Modelo and Modelo.objects.filter(pk=pk).first()
        if not o:
            return "", False
        return (f"el {tipo} {o.codigo}", _puede(lambda: permisos.puede_ver_finanzas(viewer)))

    return "", False


def _url(app: str, ruta: str, app_de_quien_mira: str) -> str:
    """El enlace a la pantalla: relativo si es de esta misma app, absoluto si es
    de la otra (una pantalla de El Taller vista desde La Gerencia)."""
    if not ruta:
        return ""
    if not app or app == app_de_quien_mira:
        return ruta
    try:
        from django.conf import settings

        base = {
            "taller": getattr(settings, "TALLER_URL", "https://taller.learningcenter.mx/"),
            "gerencia": getattr(settings, "GERENCIA_URL", "https://gerencia.learningcenter.mx/"),
        }.get(app, "")
    except Exception:  # noqa: BLE001
        base = ""
    return (base.rstrip("/") + ruta) if base else ""


def _pantalla(usuario, viewer, app_de_quien_mira: str, memo: dict) -> tuple[str, str]:
    """(qué está haciendo, enlace). ('', '') si no hay una pantalla reconocible."""
    app = getattr(usuario, "actividad_app", "") or ""
    nombre = getattr(usuario, "actividad_url_name", "") or ""
    if nombre in ("", ENTRADA, SALIDA):
        return "", ""
    regla = _PANTALLAS_APP.get((app, nombre)) or _PANTALLAS.get(nombre)
    if not regla:
        return "", ""
    ver, editar, tipo = regla
    verbo = editar if (getattr(usuario, "actividad_accion", "") or "") == "editar" else ver
    if not tipo:
        return verbo, ""

    kwargs = getattr(usuario, "actividad_kwargs", None) or {}
    pk = kwargs.get("pk")
    llave = (tipo, str(pk))
    if llave not in memo:
        try:
            memo[llave] = _objeto(tipo, pk, viewer)
        except Exception:  # noqa: BLE001 — un nombre que no se puede leer no tumba nada
            memo[llave] = ("", False)
    texto, visible = memo[llave]
    if texto and visible:
        ruta = getattr(usuario, "actividad_ruta", "") or ""
        return f"{verbo} {texto}", _url(app, ruta, app_de_quien_mira)
    return f"{verbo} {_GENERICO.get(tipo, 'algo')}", ""


def describir(usuario, viewer=None, ahora=None, memo: dict | None = None,
              app_de_quien_mira: str | None = None) -> dict:
    """Todo lo que se pinta de la presencia de una persona.

    `viewer` es quien mira (decide qué nombres puede ver); None es la pared de El
    Vigía. Quien llama ya comprobó el permiso `(equipo, ver_actividad)`: esto no
    lo vuelve a preguntar para no pagar la consulta N veces en una lista.
    """
    from django.utils import timezone

    if ahora is None:
        ahora = timezone.now()
    if memo is None:
        memo = {}
    if app_de_quien_mira is None:
        app_de_quien_mira = app_actual()

    estado = estado_de(usuario, ahora)
    cuando = getattr(usuario, "actividad_en", None)
    app = getattr(usuario, "actividad_app", "") or ""
    ruta = getattr(usuario, "actividad_ruta", "") or ""
    nombre_url = getattr(usuario, "actividad_url_name", "") or ""
    seccion = _seccion(app, ruta, nombre_url) if cuando else ""
    pantalla, url = _pantalla(usuario, viewer, app_de_quien_mira, memo) if cuando else ("", "")
    disp = dispositivo(getattr(usuario, "actividad_agente", "") or "")
    app_label = ETIQUETA_APP.get(app, "")

    # El renglón corto: «El Taller · editando LC-0044 · Gorras Cruz Azul». La
    # sección se omite cuando la pantalla ya la dice («en Mensajes» no necesita
    # «Mensajes» antes).
    partes = [app_label] if app_label else []
    if pantalla:
        partes.append(pantalla)
    elif seccion:
        partes.append(seccion)

    return {
        "usuario": usuario,
        # El nombre ya resuelto: las plantillas no pueden hacer
        # `nombre_completo|default:usuario.email`, porque un argumento de filtro
        # no se silencia si falta (candado en tests/site/test_vigia.py).
        "nombre": getattr(usuario, "nombre_completo", "") or getattr(usuario, "email", "") or "",
        "estado": estado,
        "estado_label": ESTADOS[estado]["label"],
        "orden": ESTADOS[estado]["orden"],
        "en_linea": estado == "en_linea",
        "cuando": cuando,
        "hace": hace(cuando, ahora) if cuando else "",
        "app": app,
        "app_label": app_label,
        "seccion": seccion,
        "pantalla": pantalla,
        "url": url,
        "dispositivo": disp,
        "resumen": " · ".join(partes),
    }


def equipo_ahora(viewer=None, ahora=None) -> list[dict]:
    """La presencia de todo el equipo activo: en línea primero, luego ausentes,
    luego desconectados; dentro de cada grupo, el más reciente arriba."""
    from django.db.models import F
    from django.utils import timezone

    from cuentas.models.usuario import Usuario

    if ahora is None:
        ahora = timezone.now()
    memo: dict = {}
    app = app_actual()
    usuarios = (
        Usuario.objects.filter(is_active=True)
        .order_by(F("actividad_en").desc(nulls_last=True), "nombre_completo")
    )
    items = [describir(u, viewer=viewer, ahora=ahora, memo=memo, app_de_quien_mira=app)
             for u in usuarios]
    # Orden estable: el de la consulta (más reciente primero) se conserva dentro
    # de cada estado.
    items.sort(key=lambda d: d["orden"])
    return items


def conteo(items: list[dict]) -> dict:
    """{en_linea, ausente, desconectado, nunca}."""
    salida = {clave: 0 for clave in ESTADOS}
    for item in items:
        salida[item["estado"]] = salida.get(item["estado"], 0) + 1
    return salida


def para_chalan(item: dict) -> dict:
    """Lo que se le cuenta a El Chalán de una persona — sin enlaces ni objetos."""
    return {
        "nombre": item["nombre"],
        "estado": item["estado_label"],
        "ultima_actividad": item["hace"] or "sin actividad registrada",
        "app": item["app_label"],
        "seccion": item["seccion"],
        "pantalla": item["pantalla"],
        "dispositivo": item["dispositivo"]["texto"],
    }


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para buscar a una persona por su nombre."""
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c)).lower().strip()


__all__ = [
    "AUSENTE_S", "EN_LINEA_S", "ENTRADA", "SALIDA", "URL_NAMES_SONDEO",
    "app_actual", "conteo", "describir", "dispositivo", "equipo_ahora",
    "es_sondeo", "estado_de", "hace", "marcar_entrada", "marcar_salida",
    "normalizar", "para_chalan", "registrar", "ruta_de_pantalla", "toca_escribir",
]
