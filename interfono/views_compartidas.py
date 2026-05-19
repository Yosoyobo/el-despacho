"""Vistas compartidas por las 3 apps (La Gerencia, El Taller, La Recepción).

- `sw_js`: sirve el service worker en `/sw.js` con `Service-Worker-Allowed: /`.
- `suscribir`: alta de suscripción para el usuario autenticado.
- `desuscribir`: baja de una suscripción del usuario autenticado.
- `prueba`: envía notificación de prueba al usuario actual.

Las plantillas y formas concretas viven en cada app local. Estas vistas son
endpoints JSON / texto, sin dependencia de templates.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from interfono.sw_js import sw_js  # noqa: F401  (re-export para urls_compartidas)


@login_required
@require_http_methods(["POST"])
def suscribir(request: HttpRequest) -> JsonResponse:
    """Alta de suscripción. JSON: {endpoint, keys: {p256dh, auth}}."""
    from interfono.models import InterfonoSuscripcion

    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not (endpoint and p256dh and auth):
        return JsonResponse({"error": "endpoint y keys requeridos"}, status=400)

    user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]

    sub, creada = InterfonoSuscripcion.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "usuario": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
            "activa": True,
            "desactivada_en": None,
        },
    )
    return JsonResponse({"ok": True, "id": sub.pk, "creada": creada})


@login_required
@require_http_methods(["POST"])
def desuscribir(request: HttpRequest, sub_id: int) -> JsonResponse:
    from interfono.models import InterfonoSuscripcion

    sub = InterfonoSuscripcion.objects.filter(pk=sub_id, usuario=request.user).first()
    if not sub:
        return JsonResponse({"error": "no encontrada"}, status=404)
    from django.utils import timezone

    sub.activa = False
    sub.desactivada_en = timezone.now()
    sub.save(update_fields=["activa", "desactivada_en"])
    return JsonResponse({"ok": True})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def marcar_clickeado(request: HttpRequest, entrega_id: int) -> JsonResponse:
    """Marca una entrega como clickeada. Idempotente.

    El Service Worker invoca este endpoint en `notificationclick` antes de
    abrir la URL final, para que el historial muestre el estado correcto.
    CSRF exempt: el SW no puede obtener token; el efecto (marcar la propia
    entrega del usuario autenticado) es benigno incluso si fuera forjado.
    """
    from django.utils import timezone

    from interfono.models import InterfonoEntrega

    entrega = InterfonoEntrega.objects.filter(
        pk=entrega_id, usuario=request.user
    ).first()
    if not entrega:
        return JsonResponse({"error": "no encontrada"}, status=404)
    if not entrega.clickeado_en:
        entrega.clickeado_en = timezone.now()
        entrega.save(update_fields=["clickeado_en"])
    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST"])
def prueba(request: HttpRequest) -> JsonResponse:
    """Envía notificación de prueba al usuario autenticado."""
    from lib.interfono import InterfonoConfig, enviar_a_usuario

    if not InterfonoConfig.esta_configurado():
        return JsonResponse({"error": "Notificaciones no configuradas"}, status=503)

    totales = enviar_a_usuario(
        request.user,
        titulo="Prueba — El Despacho",
        cuerpo="Esta es una notificación de prueba. Si la ves, todo está bien.",
        url="/",
        tag=f"prueba-{request.user.pk}",
    )
    return JsonResponse({"ok": True, **totales})
