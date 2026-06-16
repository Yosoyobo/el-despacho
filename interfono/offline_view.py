"""Página offline dedicada del PWA, servida en `/offline/`.

El service worker (ver `sw_js.py`) precachea esta ruta y la sirve como
fallback cuando una navegación falla sin red y la ruta pedida no está en
caché. Antes caía al `/` genérico; ahora muestra un mensaje claro de
"Sin conexión" con el branding.

Es autocontenida (CSS inline, anti-FOUC de dark mode inline) para no
depender de estáticos que quizá no estén cacheados. El único asset
externo es el logo, que sí está en el precache del SW; se resuelve con
`static()` (hasheado en prod) e inyecta para que coincida con la URL
cacheada. Sin auth: la sirven las 3 apps (incluida La Recepción stub).
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

_OFFLINE_HTML = """<!doctype html>
<html lang="es-mx">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Sin conexión — El Despacho</title>
<script>
// Anti-FOUC: aplica el tema guardado antes del primer paint (mismo criterio que base.html).
(function(){try{var g=localStorage.getItem('despacho-tema');var d=document.documentElement;
if(g==='dark'){d.classList.add('dark');}else if(g==='light'){d.classList.remove('dark');}
else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches){d.classList.add('dark');}}catch(e){}})();
</script>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font-family:'Outfit',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
background:#f9fafb;color:#1d2939;display:flex;align-items:center;justify-content:center;
padding:max(env(safe-area-inset-top),1.5rem) 1.5rem max(env(safe-area-inset-bottom),1.5rem);
min-height:100dvh;text-align:center}
html.dark body{background:#0c111d;color:#e4e7ec}
.caja{max-width:24rem;width:100%}
.logo{width:72px;height:72px;margin:0 auto 1.5rem;opacity:.9}
h1{font-size:1.375rem;font-weight:600;margin:0 0 .5rem}
p{font-size:.9375rem;line-height:1.55;color:#667085;margin:0 0 1.75rem}
html.dark p{color:#98a2b3}
.btn{display:inline-block;cursor:pointer;border:0;border-radius:.625rem;
background:#465fff;color:#fff;font-size:.9375rem;font-weight:500;
padding:.7rem 1.5rem;font-family:inherit;transition:background .15s}
.btn:hover{background:#3a4fd6}
.hint{margin-top:1.25rem;font-size:.75rem;color:#98a2b3}
html.dark .hint{color:#667085}
.dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;background:#f79009;margin-right:.4rem;vertical-align:middle}
</style>
</head>
<body>
<div class="caja">
<img class="logo" src="__LOGO__" alt="Learning Center">
<h1><span class="dot"></span>Sin conexión</h1>
<p>No pudimos cargar esta página porque tu dispositivo no tiene internet en este momento. El Despacho seguirá aquí cuando vuelva la conexión.</p>
<button class="btn" onclick="location.reload()">Reintentar</button>
<p class="hint">Tip: las checadas de El Checador se guardan en tu dispositivo aunque estés sin conexión y se sincronizan solas al reconectar.</p>
</div>
</body>
</html>
"""


def offline(request: HttpRequest) -> HttpResponse:
    from django.templatetags.static import static

    try:
        logo = static("branding/Logo_LC-192.png")
    except Exception:  # noqa: BLE001 — asset ausente: degrada sin logo
        logo = ""
    html = _OFFLINE_HTML.replace("__LOGO__", logo)
    resp = HttpResponse(html, content_type="text/html; charset=utf-8")
    # El SW la precachea; no la queremos pegada en el http-cache del navegador.
    resp["Cache-Control"] = "no-cache"
    return resp
