"""Impersonación para desarrollo/soporte (S-LC-Feedback-V8).

Un super_admin puede "ver el sistema como" otro usuario para reproducir bugs.
Mientras impersona, `request.user` ES el usuario objetivo (todos los gates,
permisos y vistas se comportan como para esa persona). Se preserva al
super_admin real en `request.impersonador` para el banner y la salida.

Reglas de seguridad:
- Solo un super_admin REAL puede iniciar/estar impersonando (se revalida en
  cada request; si pierde el rol, la sesión se limpia).
- No se puede impersonar a otro super_admin (evita escalamiento lateral).
- Hay un banner siempre visible con un botón para salir.
"""

from __future__ import annotations

SESSION_KEY = "impersonate_id"
# S-Roles-V2: "ver como rol" — simula un ROL (no un usuario) para debug/QA.
ROL_SIM_KEY = "ver_como_rol"


class ImpersonacionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.impersonando = None
        request.impersonador = None
        request.rol_simulado = None
        imp_id = request.session.get(SESSION_KEY)
        if imp_id and getattr(request.user, "is_authenticated", False):
            from lib.permisos import tiene_rol
            # request.user aquí es el super_admin REAL (lo puso AuthMiddleware).
            if tiene_rol(request.user, "super_admin"):
                from cuentas.models.usuario import Usuario
                objetivo = Usuario.objects.filter(pk=imp_id, is_active=True).first()
                if objetivo is None or tiene_rol(objetivo, "super_admin"):
                    request.session.pop(SESSION_KEY, None)
                else:
                    request.impersonador = request.user
                    request.user = objetivo
                    request.impersonando = objetivo
            else:
                # El usuario real ya no es super_admin: corta la impersonación.
                request.session.pop(SESSION_KEY, None)

        # "Ver como rol": simula un rol SIN cambiar de usuario. Solo si NO está
        # impersonando a otra persona y el usuario real es super_admin (se valida
        # ANTES de marcar el flag, con los roles reales). El flag `_rol_simulado`
        # lo leen `lib.permisos.roles_efectivos` y `puede`. La SALIDA no se gatea
        # por permiso, así que el super_admin siempre puede volver (y el home del
        # Taller es login-only → puerto seguro).
        if request.impersonando is None:
            rol_sim = request.session.get(ROL_SIM_KEY)
            if rol_sim and getattr(request.user, "is_authenticated", False):
                from lib.permisos import tiene_rol
                if tiene_rol(request.user, "super_admin"):
                    request.user._rol_simulado = rol_sim
                    request.rol_simulado = rol_sim
                else:
                    request.session.pop(ROL_SIM_KEY, None)
        return self.get_response(request)
