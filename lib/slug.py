"""Generación de slugs para el Sistema de Referencias (@/#/$).

- Usuario → desde email antes del `@`, kebab-case sin acentos.
- Cliente → desde razón social, kebab-case sin acentos, max 50 chars.
- Proyecto → directo del código en minúsculas (`PRY-000123` → `pry-000123`).

Si la generación produce un slug ya tomado, sufija `-2`, `-3`, … hasta encontrar
uno libre. La unicidad final la garantiza la DB (UniqueConstraint).
"""

from __future__ import annotations

import re
import unicodedata


def _normalizar(texto: str) -> str:
    """Quita acentos, baja a minúsculas, colapsa a kebab-case [a-z0-9-]."""
    if not texto:
        return ""
    # Descompone tildes (NFD), elimina combining marks
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    bajo = sin_acentos.lower()
    # Sustituye cualquier no-alfanumérico por guión, colapsa repetidos
    kebab = re.sub(r"[^a-z0-9]+", "-", bajo).strip("-")
    return kebab


def _desambiguar(base: str, modelo, exclude_id=None) -> str:
    """Si `base` ya existe en `modelo.slug`, agrega -2, -3, … hasta libre."""
    if not base:
        base = "usuario"
    qs = modelo.objects.filter(slug=base)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    if not qs.exists():
        return base
    n = 2
    while True:
        candidato = f"{base}-{n}"
        qs = modelo.objects.filter(slug=candidato)
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if not qs.exists():
            return candidato
        n += 1
        if n > 9999:  # defensivo, no debería pasar en producción humana
            raise RuntimeError(f"No se pudo desambiguar slug base={base}")


def generar_slug_usuario(usuario) -> str:
    from cuentas.models.usuario import Usuario

    base_email = (usuario.email or "").split("@", 1)[0]
    base = _normalizar(base_email)[:60] or "usuario"
    return _desambiguar(base, Usuario, exclude_id=usuario.pk)


def generar_slug_cliente(cliente) -> str:
    from apps.la_cartera.models.cliente import Cliente

    base = _normalizar(cliente.razon_social or "")[:50] or "cliente"
    return _desambiguar(base, Cliente, exclude_id=cliente.pk)


def generar_slug_proyecto(proyecto) -> str:
    from apps.los_proyectos.models.proyecto import Proyecto

    codigo = (proyecto.codigo or "").lower()
    base = _normalizar(codigo) or "proyecto"
    return _desambiguar(base, Proyecto, exclude_id=proyecto.pk)
