"""register_or_link_google_user — regla #16 del proyecto.

Si el email del perfil Google matchea con un Usuario activo en El Directorio,
vincula la cuenta Google al Usuario. Si no, lanza
`GoogleOAuthCuentaNoRegistrada` (NO autoregistro).

Casos cubiertos:
- Match por `google_sub` ya vinculado → retorna sin update (caso común).
- Match por `email` y aún sin `google_sub` → vincula y emite Portavoz.
- Usuario inactivo → CuentaNoRegistrada (no filtra info de cuentas baneadas).
- Usuario con `google_sub` distinto → YaVinculadoAOtra (no sobrescribe).
"""

from __future__ import annotations

import logging

from django.utils import timezone

from cuentas.models.usuario import Usuario
from lib.google_oauth import (
    GoogleOAuthCuentaNoRegistrada,
    GoogleOAuthYaVinculadoAOtra,
    PerfilGoogle,
)
from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz

logger = logging.getLogger(__name__)


def register_or_link_google_user(perfil: PerfilGoogle) -> Usuario:
    # 1. Caso común: ya vinculado por google_sub.
    user = Usuario.objects.filter(google_sub=perfil.sub).first()
    if user is not None:
        if not user.is_active:
            raise GoogleOAuthCuentaNoRegistrada(perfil.email)
        return user

    # 2. Primer link: buscar por email activo.
    user = Usuario.objects.filter(email__iexact=perfil.email, is_active=True).first()
    if user is None:
        try:
            emitir(EventoPortavoz(
                tipo="auth.google_cuenta_no_registrada",
                actor_id=None,
                actor_email=None,
                payload={"google_email": perfil.email, "google_sub": perfil.sub},
            ))
        except Exception:
            logger.warning("portavoz: no se pudo emitir auth.google_cuenta_no_registrada", exc_info=True)
        raise GoogleOAuthCuentaNoRegistrada(perfil.email)

    # 3. Si ese Usuario ya tiene google_sub distinto, no sobrescribir.
    if user.google_sub and user.google_sub != perfil.sub:
        raise GoogleOAuthYaVinculadoAOtra(perfil.email)

    user.google_sub = perfil.sub
    user.google_email = perfil.email
    user.google_vinculado_en = timezone.now()
    if not user.avatar_url and perfil.foto_url:
        user.avatar_url = perfil.foto_url
        update_fields = ["google_sub", "google_email", "google_vinculado_en", "avatar_url"]
    else:
        update_fields = ["google_sub", "google_email", "google_vinculado_en"]
    user.save(update_fields=update_fields)

    try:
        emitir(EventoPortavoz(
            tipo="auth.google_vinculada",
            actor_id=user.pk,
            actor_email=user.email,
            payload={"google_email": perfil.email, "google_sub": perfil.sub},
        ))
    except Exception:
        logger.warning("portavoz: no se pudo emitir auth.google_vinculada", exc_info=True)

    return user
