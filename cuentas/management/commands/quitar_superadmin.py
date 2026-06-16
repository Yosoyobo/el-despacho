"""Quita el rol super_admin a un usuario (pedido de Oscar: "Quítale a Jorge").

Hace dos cosas, ambas idempotentes:
  1. Si el rol PRIMARIO es `super_admin`, lo baja a `miembro` (rol neutro, V6).
  2. Quita de `roles_extra` cualquier Rol llamado `super_admin` (por si el
     acceso venía por un rol personalizado en lugar del primario).

Los permisos efectivos se recalculan solos vía `lib.permisos.roles_efectivos`
(no hay caché que invalidar). NO toca permisos individuales (`PermisoUsuario`).

Uso (en La Sede, dentro del contenedor el-taller o la-gerencia):
    python manage.py quitar_superadmin --email jorge@learningcenter.mx
    python manage.py quitar_superadmin --buscar jorge        # por nombre/email

Atajo equivalente sin deploy: La Gerencia → El Directorio → Jorge → pestaña
Datos → rol = "Miembro". Este comando existe para hacerlo desde consola.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Quita super_admin (rol primario y/o roles_extra) a un usuario."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="", help="Email exacto del usuario.")
        parser.add_argument("--buscar", default="",
                            help="Fragmento de nombre o email (debe coincidir con 1 solo).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Reporta sin guardar cambios.")

    def handle(self, *args, **opts):
        from cuentas.models.usuario import Usuario

        email = (opts["email"] or "").strip()
        buscar = (opts["buscar"] or "").strip()
        if not email and not buscar:
            raise CommandError("Pasa --email o --buscar.")

        qs = Usuario.objects.all()
        if email:
            qs = qs.filter(email__iexact=email)
        else:
            from django.db.models import Q
            qs = qs.filter(Q(email__icontains=buscar) | Q(nombre_completo__icontains=buscar))

        usuarios = list(qs)
        if not usuarios:
            raise CommandError("No se encontró ningún usuario con ese criterio.")
        if len(usuarios) > 1:
            nombres = ", ".join(f"{u.email} ({u.nombre_completo})" for u in usuarios)
            raise CommandError(f"Coincidió con {len(usuarios)} usuarios — acota: {nombres}")

        u = usuarios[0]
        cambios = []

        if u.rol == "super_admin":
            cambios.append(f"rol primario super_admin → miembro")
            if not opts["dry_run"]:
                u.rol = "miembro"
                u.save(update_fields=["rol"])

        extras = list(u.roles_extra.filter(nombre="super_admin"))
        if extras:
            cambios.append(f"quitar {len(extras)} rol(es) extra 'super_admin'")
            if not opts["dry_run"]:
                u.roles_extra.remove(*extras)

        prefijo = "[dry] " if opts["dry_run"] else ""
        if not cambios:
            self.stdout.write(f"{u.email} no tiene super_admin (nada que hacer).")
            return
        for c in cambios:
            self.stdout.write(f"{prefijo}{u.email}: {c}")
        self.stdout.write(self.style.SUCCESS(
            f"{prefijo}Listo. Rol primario ahora: {u.rol}."))
