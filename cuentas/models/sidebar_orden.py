"""S-LC-Feedback-V5 c6 — Orden global de items del sidebar del Taller.

Una fila por slug. El super_admin reordena/oculta items desde
`/ajustes/sidebar/` en La Gerencia. El context processor inyecta
`sidebar_orden` como dict `{slug: {orden, oculto}}` y el template
aplica `style="order: N"` (flexbox) + `{% if not oculto %}` por item.
"""

from __future__ import annotations

from django.db import models

# Slugs canónicos del sidebar del Taller. Si agregas un item nuevo,
# añade aquí su slug + label (label es solo informativo en la UI de
# /ajustes/sidebar/; el sidebar template sigue siendo HTML estático
# por item — sólo cambia el orden CSS y la visibilidad).
SLUGS_SIDEBAR_TALLER = [
    ("dashboard", "Dashboard"),
    ("clientes", "Clientes"),
    ("proyectos", "Proyectos"),
    ("calendario", "Calendario"),
    ("directorio", "Directorio"),
    ("buzon", "Buzón"),
    ("recados", "Recados"),
    ("chat", "El Chalán (chat IA)"),
    ("productos", "Productos"),
    ("notificaciones", "Notificaciones"),
    ("chalanes", "Chalanes"),
    ("cotizaciones", "Cotizaciones"),
    ("finanzas", "Finanzas (grupo: Tesorería/Facturación/Contaduría)"),
    ("ajustes", "Ajustes (atajo a Gerencia)"),
    ("ayuda", "Ayuda"),
]


class SidebarOrden(models.Model):
    slug = models.CharField(max_length=40, unique=True, db_index=True)
    orden = models.PositiveIntegerField(default=100, db_index=True)
    oculto = models.BooleanField(default=False)

    class Meta:
        db_table = "cuentas_sidebar_orden"
        ordering = ["orden", "slug"]

    def __str__(self) -> str:
        return f"{self.slug} #{self.orden}{' (oculto)' if self.oculto else ''}"
