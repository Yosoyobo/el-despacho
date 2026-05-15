"""Genera un par de llaves VAPID y las guarda en La Bóveda.

Idempotente al sentido inverso: falla si ya hay llaves para evitar invalidar
sin querer todas las suscripciones existentes. Para regenerar: borrar primero
los slots `vapid_public_key` y `vapid_private_key` en Los Ajustes.
"""

from __future__ import annotations

import base64

from django.core.management.base import BaseCommand, CommandError


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _generar_par() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_b64 = _b64url(private_key.private_numbers().private_value.to_bytes(32, "big"))

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = _b64url(public_bytes)
    _ = pem  # PEM no se persiste; pywebpush acepta el escalar privado base64url.
    return public_b64, private_b64


class Command(BaseCommand):
    help = "Genera llaves VAPID y las guarda cifradas en Los Ajustes."

    def handle(self, *args, **opts):
        from ajustes.models.credencial import Credencial

        if Credencial.esta_configurado("vapid_public_key") or Credencial.esta_configurado("vapid_private_key"):
            raise CommandError(
                "Ya existen llaves VAPID. Para regenerar, primero borrarlas "
                "manualmente desde Los Ajustes (eso invalidará TODAS las "
                "suscripciones existentes)."
            )

        public_b64, private_b64 = _generar_par()
        Credencial.guardar("vapid_public_key", public_b64)
        Credencial.guardar("vapid_private_key", private_b64)
        if not Credencial.esta_configurado("vapid_email"):
            Credencial.guardar("vapid_email", "mailto:soporte@bautista.mx")

        self.stdout.write(self.style.SUCCESS(
            "Llaves VAPID generadas y guardadas. Public key disponible vía "
            "InterfonoConfig.vapid_public_key()."
        ))
