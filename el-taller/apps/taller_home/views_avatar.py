"""Avatar del usuario (S-LC-Feedback-V8).

El usuario sube su foto; se guarda en Google Drive (privado, subcarpeta
"Avatares") y se sirve por un proxy autenticado — mismo patrón que los
adjuntos del repo (los archivos de Drive no se hacen públicos). `avatar_url`
apunta al proxy `/perfil/avatar-img/<file_id>`.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

# Solo imágenes para el avatar.
MIME_IMAGEN = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "image/heic", "image/heif"}
LIMITE_AVATAR = 8 * 1024 * 1024  # 8 MB


@login_required
def avatar_modal(request):
    """GET/POST /perfil/avatar/ — cambia la foto del usuario actual."""
    if request.method == "POST":
        archivo = request.FILES.get("avatar")
        if not archivo:
            messages.error(request, "Elige una imagen.")
            return _render_modal(request, "Elige una imagen.")
        mime = (getattr(archivo, "content_type", "") or "").lower()
        if mime and mime not in MIME_IMAGEN:
            return _render_modal(request, "Solo se permiten imágenes (PNG, JPG, WEBP, GIF).")
        if getattr(archivo, "size", 0) > LIMITE_AVATAR:
            return _render_modal(request, "La imagen pesa más de 8 MB.")

        from lib.adjuntos import subir
        res = subir(archivo, subcarpeta="Avatares")
        if not res.ok:
            return _render_modal(request, res.error or "No se pudo subir la imagen a Drive.")

        file_id = (res.data or {}).get("id", "")
        if not file_id:
            return _render_modal(request, "Drive no devolvió el archivo.")

        # Borra el avatar anterior (best-effort).
        viejo = request.user.avatar_drive_id
        request.user.avatar_drive_id = file_id
        request.user.avatar_url = reverse("perfil-avatar-img", args=[file_id])
        request.user.save(update_fields=["avatar_drive_id", "avatar_url"])
        if viejo and viejo != file_id:
            try:
                from lib.google_drive import drive
                drive.borrar(viejo)
            except Exception:  # noqa: BLE001
                pass
        messages.success(request, "Tu foto se actualizó.")
        if request.headers.get("HX-Request") == "true":
            return HttpResponse(status=204, headers={"HX-Redirect": reverse("directorio-perfil", args=[request.user.pk])})
        return _render_modal(request, "")

    return _render_modal(request, "")


def _render_modal(request, error: str):
    return render(request, "taller_home/_modal_avatar.html", {"error_avatar": error})


@login_required
def avatar_img(request, file_id: str):
    """Proxy autenticado: sirve la imagen del avatar desde Drive.

    Seguridad: solo sirve file_ids que sean el avatar de ALGÚN usuario (no
    permite leer archivos arbitrarios de Drive). Cachea en el navegador.
    """
    from cuentas.models.usuario import Usuario
    if not Usuario.objects.filter(avatar_drive_id=file_id).exists():
        return HttpResponse(status=404)
    try:
        from lib.google_drive import drive
        contenido, mime, _ = drive.descargar(file_id)
    except Exception:  # noqa: BLE001
        return HttpResponse(status=404)
    resp = HttpResponse(contenido, content_type=mime or "image/jpeg")
    resp["Cache-Control"] = "private, max-age=86400"
    return resp
