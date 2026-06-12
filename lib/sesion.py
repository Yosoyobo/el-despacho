"""getAuth() consistente — devuelve un ContextoUsuario o None.

Spec original (Next.js) usaba JWT con `jose`. Adaptado a Django: lee de
`request.user`. Mantiene la misma forma de retorno para que el código de vistas
se vea uniforme entre apps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.http import HttpRequest

from lib.permisos import roles_efectivos


@dataclass(frozen=True)
class ContextoUsuario:
    id: int
    email: str
    nombre: str
    rol: str
    activo: bool
    # V6 Bloque 10: roles efectivos (rol primario + roles_extra) capturados
    # en getAuth(). El dataclass no carga el user, así que el set viaja aquí.
    roles: frozenset[str] = field(default_factory=frozenset)

    @property
    def es_admin(self) -> bool:
        # V6 Bloque 10: reconoce roles personalizados además del rol primario.
        return bool(({self.rol} | self.roles) & {"super_admin", "dueno"})

    @property
    def es_super_admin(self) -> bool:
        # V6 Bloque 10: idem — super_admin puede venir como rol personalizado.
        return "super_admin" in ({self.rol} | self.roles)


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
        # V6 Bloque 10: une rol primario + roles_extra (defensivo si no hay M2M).
        roles=frozenset(roles_efectivos(user)),
    )
