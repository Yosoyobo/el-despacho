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
"""


def sw_js(request: HttpRequest) -> HttpResponse:
    resp = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp
