"""Contenido y view del service worker, sin dependencias de auth.

Se separa de `views_compartidas` para que La Recepción (que no tiene
`django.contrib.auth` en INSTALLED_APPS) pueda servirlo sin importar
decoradores de auth.

`SERVICE_WORKER_JS` es la parte de comportamiento (push web + caché offline del
shell). La cabecera con la lista de precache y el nombre de caché versionado se
inyecta por request en `sw_js()` (los estáticos van hasheados en producción, así
que deben resolverse con `static()` en cada respuesta).
"""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse

# Assets del shell a precachear (S4 — caché offline). Se resuelven con
# `static()` (hasheados en prod). Cada uno va guardado con try/except: un asset
# ausente en una app (p. ej. Gerencia no tiene checador.js) NO rompe el SW.
_PRECACHE_CANDIDATOS = [
    "css/tailwind.css",
    "js/tema.js",
    "js/ui.js",
    "js/form_widgets.js",
    "js/textarea_ia.js",
    "manifest.json",
    "branding/Logo_LC-192.png",
    "branding/Logo_LC-64.png",
    "branding/Icono_LC-192.png",
]

SERVICE_WORKER_JS = """// El Interfono — service worker (push web + caché offline del shell).
// Convención del tag (front-end):
//   - mensajes manuales: 'manual-<envio_id>'  → un nuevo manual reemplaza al previo del mismo envio
//   - mensajes automáticos futuros: 'auto-<tipo>-<id>'
// Si no llega tag en el payload, generamos uno único para evitar colapso.
// La cabecera (server-side) define DESPACHO_CACHE y DESPACHO_PRECACHE.

self.addEventListener('push', function(event) {
    if (!event.data) return;
    let data;
    try { data = event.data.json(); } catch (e) { data = { title: 'El Despacho', body: event.data.text() }; }
    const tag = data.tag || ('el-despacho-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8));
    const opciones = {
        body: data.body || '',
        icon: data.icon || '/static/branding/Logo_LC-192.png',
        badge: data.badge || '/static/branding/Logo_LC-64.png',
        data: { url: data.url || '/', entrega_id: data.entrega_id || null },
        tag: tag,
    };
    // Badge del ícono de la app (App Badging API). Si el payload trae
    // `badge_count` lo usamos; si no, marcamos un punto genérico. El cliente
    // sincroniza el número exacto al abrir/navegar (ver base.html).
    let tareas = self.registration.showNotification(data.title || 'El Despacho', opciones);
    if (self.navigator && self.navigator.setAppBadge) {
        const n = parseInt(data.badge_count, 10);
        tareas = Promise.all([
            tareas,
            (Number.isFinite(n) ? self.navigator.setAppBadge(n) : self.navigator.setAppBadge()).catch(function(){}),
        ]);
    }
    event.waitUntil(tareas);
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const data = event.notification.data || {};
    const url = data.url || '/';
    const entregaId = data.entrega_id;
    const marcar = entregaId
        ? fetch('/perfil/notificaciones/' + entregaId + '/clickeado', {
            method: 'POST',
            credentials: 'include',
            headers: {'X-CSRFToken': '', 'X-Despacho-SW': '1'},
          }).catch(function() {})
        : Promise.resolve();
    event.waitUntil(marcar.then(function() { return clients.openWindow(url); }));
});

// ── Caché offline del shell (S4) ──────────────────────────────────────────────
// Estrategia: navegación = network-first (cae a caché o a '/' si no hay red,
// nunca pantalla en blanco); /static/ = cache-first con relleno runtime; el
// resto (APIs, polling, POST) = passthrough sin tocar. No rompe el push.
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(DESPACHO_CACHE).then(function(cache) {
            // add tolerante: un 404 de un asset no aborta el resto del precache.
            return Promise.all(DESPACHO_PRECACHE.map(function(u) {
                return cache.add(u).catch(function() {});
            }));
        }).then(function() { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(claves) {
            return Promise.all(claves.map(function(k) {
                if (k.indexOf('despacho-shell-') === 0 && k !== DESPACHO_CACHE) {
                    return caches.delete(k);
                }
                return null;
            }));
        }).then(function() { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function(event) {
    const req = event.request;
    if (req.method !== 'GET') return;  // no tocar POST/PUT (CSRF, mutaciones)
    let url;
    try { url = new URL(req.url); } catch (e) { return; }
    if (url.origin !== self.location.origin) return;  // cross-origin passthrough (CDN/fonts)

    // Navegación: network-first; offline → caché de la ruta, si no la página
    // dedicada '/offline/', y como último recurso el shell '/'.
    if (req.mode === 'navigate') {
        event.respondWith(
            fetch(req).catch(function() {
                return caches.match(req).then(function(r) {
                    if (r) return r;
                    return caches.match(DESPACHO_OFFLINE).then(function(o) { return o || caches.match('/'); });
                });
            })
        );
        return;
    }

    // Estáticos hasheados: cache-first con relleno al vuelo.
    if (url.pathname.indexOf('/static/') === 0) {
        event.respondWith(
            caches.match(req).then(function(cached) {
                return cached || fetch(req).then(function(resp) {
                    if (resp && resp.ok) {
                        const copia = resp.clone();
                        caches.open(DESPACHO_CACHE).then(function(c) { c.put(req, copia); });
                    }
                    return resp;
                });
            })
        );
        return;
    }
    // Resto: passthrough (no cachear datos dinámicos / polling del chat).
});
"""


def _cabecera() -> str:
    """Define `DESPACHO_CACHE` (versionado) y `DESPACHO_PRECACHE` (assets
    resueltos con `static()`, hasheados en prod). Guarda cada asset: uno
    ausente se omite sin romper el SW."""
    from django.templatetags.static import static

    from lib.version import VERSION
    assets: list[str] = []
    for ruta in _PRECACHE_CANDIDATOS:
        try:
            assets.append(static(ruta))
        except Exception:  # noqa: BLE001 — asset ausente en esta app: se omite
            continue
    assets.append("/")
    assets.append("/offline/")  # página dedicada de "sin conexión" (fallback de navegación)
    return (
        f'const DESPACHO_CACHE = "despacho-shell-{VERSION}";\n'
        f'const DESPACHO_OFFLINE = "/offline/";\n'
        f"const DESPACHO_PRECACHE = {json.dumps(assets)};\n\n"
    )


def sw_js(request: HttpRequest) -> HttpResponse:
    resp = HttpResponse(_cabecera() + SERVICE_WORKER_JS, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp
