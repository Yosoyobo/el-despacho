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
    ("mandados", "Mandados (envíos)"),
    ("calendario", "Calendario"),
    ("checador", "Checador"),
    ("directorio", "Equipo / Directorio"),
    ("buzon", "Buzón"),
    ("recados", "Mensajes"),
    ("chat", "El Chalán (chat IA)"),
    ("productos", "Productos"),
    ("proveedores", "Proveedores"),
    ("notificaciones", "Notificaciones"),
    ("chalanes", "Chalanes"),
    ("cotizaciones", "Cotizaciones"),
    ("campanas", "Campañas de correo"),
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


# Iconos disponibles para las carpetas del sidebar (S-LC-Feedback-V11). El
# valor guardado es la CLAVE; el SVG lo pinta `static/js/ui.js` (registro
# espejo `ICONOS_CARPETA`). El emoji es solo para el selector visual del editor.
ICONOS_CARPETA = [
    ("folder", "📁", "Carpeta"),
    ("star", "⭐", "Estrella"),
    ("rocket", "🚀", "Cohete"),
    ("money", "💰", "Dinero"),
    ("chart", "📊", "Gráfica"),
    ("wrench", "🔧", "Herramienta"),
    ("users", "👥", "Equipo"),
    ("calendar", "📅", "Calendario"),
    ("bell", "🔔", "Campana"),
    ("box", "📦", "Caja"),
    ("tag", "🏷️", "Etiqueta"),
    ("chat", "💬", "Mensajes"),
    ("heart", "❤️", "Corazón"),
    ("bolt", "⚡", "Rayo"),
    ("gear", "⚙️", "Engrane"),
    ("pin", "📌", "Pin"),
]
ICONOS_CARPETA_CLAVES = {k for k, _e, _l in ICONOS_CARPETA}


class SidebarCarpetaUsuario(models.Model):
    """S-LC-Feedback-V11 — metadatos de una carpeta del sidebar POR USUARIO.

    El orden de las carpetas se deriva del orden de sus items (ver
    `SidebarOrdenUsuario.orden`); aquí solo persistimos el ICONO elegido por el
    usuario para cada carpeta (identificada por su nombre). Sin fila → icono
    `folder` por defecto.
    """

    usuario = models.ForeignKey(
        "cuentas.Usuario", on_delete=models.CASCADE, related_name="sidebar_carpetas")
    nombre = models.CharField(max_length=40)
    icono = models.CharField(max_length=24, default="folder")

    class Meta:
        db_table = "cuentas_sidebar_carpeta_usuario"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "nombre"], name="sidebar_carpeta_usuario_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.usuario_id}:{self.nombre} ({self.icono})"
