"""getAuth() consistente — devuelve un ContextoUsuario o None.

Spec original (Next.js) usaba JWT con `jose`. Adaptado a Django: lee de
`request.user`. Mantiene la misma forma de retorno para que el código de vistas
se vea uniforme entre apps.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest


@dataclass(frozen=True)
class ContextoUsuario:
    id: int
    email: str
    nombre: str
    rol: str
    activo: bool

    @property
    def es_admin(self) -> bool:
        return self.rol in ("super_admin", "dueno")

    @property
    def es_super_admin(self) -> bool:
        return self.rol == "super_admin"


def getAuth(request: HttpRequest) -> ContextoUsuario | None:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    return ContextoUsuario(
        id=user.pk,
        email=getattr(user, "email", "") or "",
        nombre=getattr(user, "nombre_completo", "") or getattr(user, "username", ""),
        rol=getattr(user, "rol", "disenador"),
        activo=bool(getattr(user, "is_active", False)),
    )
