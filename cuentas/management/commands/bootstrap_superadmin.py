"""Crea o actualiza el super_admin inicial desde variables de entorno.
Idempotente: si ya existe, solo actualiza rol/is_active. NO sobreescribe password
existente (para no romper un login que ya esté funcionando)."""

import os

from django.core.management.base import BaseCommand

from cuentas.models.usuario import Usuario


class Command(BaseCommand):
    help = "Crea/actualiza el super_admin desde DESPACHO_SUPERADMIN_EMAIL/PASSWORD"

    def handle(self, *args, **kw):
        email = os.environ.get("DESPACHO_SUPERADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("DESPACHO_SUPERADMIN_PASSWORD", "").strip()
        if not email:
            self.stdout.write("No DESPACHO_SUPERADMIN_EMAIL — skipping.")
            return

        u = Usuario.objects.filter(email=email).first()
        if u is None:
            if not password:
                self.stdout.write(self.style.ERROR(
                    "Usuario inexistente y sin password en ENV — no se crea."
                ))
                return
            u = Usuario.objects.create_superuser(
                email=email, password=password, nombre_completo="Super Admin"
            )
            self.stdout.write(self.style.SUCCESS(f"super_admin creado: {email}"))
        else:
            u.rol = "super_admin"
            u.is_active = True
            u.is_staff = True
            u.is_superuser = True
            u.save(update_fields=["rol", "is_active", "is_staff", "is_superuser"])
            self.stdout.write(f"super_admin existente actualizado: {email}")
