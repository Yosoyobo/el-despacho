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
    ("tareas", "Tareas"),
    ("calendario", "Calendario"),
    ("checador", "Checador"),
    ("directorio", "Equipo / Directorio"),
    ("buzon", "Buzón"),
    ("recados", "Recados"),
    ("chat", "El Chalán (chat IA)"),
    ("productos", "Productos"),
    ("proveedores", "Proveedores"),
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


class SidebarOrdenUsuario(models.Model):
    """S-LC-Feedback-V7 — orden/visibilidad del sidebar POR USUARIO.

    Cada persona acomoda su propio menú desde `/perfil/sidebar/` en El Taller.
    Una fila por (usuario, slug) PISA la fila global de `SidebarOrden` para ese
    usuario. Si no hay fila personal, cae a la global y luego al default del
    template. Borrar las filas personales restablece al orden global.
    """

    usuario = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.CASCADE, related_name="sidebar_orden")
    slug = models.CharField(max_length=40, db_index=True)
    orden = models.PositiveIntegerField(default=100)
    oculto = models.BooleanField(default=False)
    # V9 — carpeta/grupo personalizado del usuario. Vacío = item suelto (top
    # level). Los items con el MISMO `grupo` se renderizan juntos en una carpeta
    # colapsable en el sidebar (vía JS, ver static/js/ui.js). El nombre del
    # grupo lo escribe el usuario en /perfil/sidebar/.
    grupo = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        db_table = "cuentas_sidebar_orden_usuario"
        ordering = ["orden", "slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "slug"], name="sidebar_orden_usuario_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario_id}:{self.slug} #{self.orden}{' (oculto)' if self.oculto else ''}"
