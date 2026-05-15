"""Contenido y view del service worker, sin dependencias de auth.

Se separa de `views_compartidas` para que La Recepción (que no tiene
`django.contrib.auth` en INSTALLED_APPS) pueda servirlo sin importar
decoradores de auth.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

SERVICE_WORKER_JS = """// El Interfono — service worker.
// Convención del tag (front-end):
//   - mensajes manuales: 'manual-<envio_id>'  → un nuevo manual reemplaza al previo del mismo envio
//   - mensajes automáticos futuros: 'auto-<tipo>-<id>'
// Si no llega tag en el payload, generamos uno único para evitar colapso.

self.addEventListener('push', function(event) {
    if (!event.data) return;
    let data;
    try { data = event.data.json(); } catch (e) { data = { title: 'El Despacho', body: event.data.text() }; }
    const tag = data.tag || ('el-despacho-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8));
    const opciones = {
        body: data.body || '',
        icon: data.icon || '/static/icons/icon-192.png',
        badge: '/static/icons/badge.png',
        data: { url: data.url || '/' },
        tag: tag,
    };
    event.waitUntil(self.registration.showNotification(data.title || 'El Despacho', opciones));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || '/';
    event.waitUntil(clients.openWindow(url));
});
"""


def sw_js(request: HttpRequest) -> HttpResponse:
    resp = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp
