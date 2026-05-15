"""Caddy — lectura del directorio de certificados (bind mount en
`/caddy:/caddy:ro`). Devuelve los certs encontrados y días hasta expiración.

En dev/tests sin bind mount, retorna `disponible=False`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CADDY_DATA = Path(os.environ.get("SITE_CADDY_DATA", "/caddy/data/caddy/certificates"))


def _cargar_cert(p: Path) -> dict[str, Any] | None:
    try:
        pem = p.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        # ssl.PEM_cert_to_DER_cert + cryptography sería más limpio, pero
        # con stdlib usamos parser básico de fechas.
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        cert = x509.load_pem_x509_certificate(pem.encode(), default_backend())
        not_after = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=UTC)
        ahora = datetime.now(UTC)
        dias = (not_after - ahora).days
        nombres = []
        try:
            ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            nombres = [d.value for d in ext.value.get_values_for_type(x509.DNSName)]
        except Exception:
            pass
        return {
            "archivo": p.name,
            "nombres": nombres or [str(cert.subject.rfc4514_string())],
            "expira_en": not_after.isoformat(),
            "dias_para_expirar": dias,
            "vence_pronto": dias < 14,
        }
    except Exception:
        # Fallback sin cryptography
        return {"archivo": p.name, "expira_en": None, "dias_para_expirar": None}


def snapshot() -> dict[str, Any]:
    if not CADDY_DATA.exists():
        return {"disponible": False, "motivo": f"{CADDY_DATA} no existe"}
    certs: list[dict[str, Any]] = []
    for p in CADDY_DATA.rglob("*.crt"):
        c = _cargar_cert(p)
        if c is not None:
            certs.append(c)
    return {"disponible": True, "ruta": str(CADDY_DATA), "certs": certs}
