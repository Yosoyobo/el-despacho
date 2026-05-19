from __future__ import annotations

from django.conf import settings
from django.db import models


class PreferenciaCategoriaPush(models.Model):
    """Opt-out por categoría de push (S2b.1).

    Default: si NO existe fila para `(usuario, categoria)`, se trata como
    activa. Sólo se persiste cuando el usuario explícitamente la desactiva
    (o la reactiva tras haberla apagado).
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferencias_push",
    )
    categoria = models.CharField(max_length=40)
    activo = models.BooleanField(default=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interfono_preferencia_categoria"
        unique_together = [("usuario", "categoria")]
        indexes = [
            models.Index(fields=["usuario", "categoria"]),
        ]

    def __str__(self) -> str:
        return f"pref u={self.usuario_id} cat={self.categoria} activo={self.activo}"


def categoria_activa(usuario, categoria: str) -> bool:
    """Opt-out: True si no hay fila o si la fila dice activo=True."""
    if not usuario or not getattr(usuario, "pk", None):
        return False
    if not categoria:
        return True
    try:
        pref = PreferenciaCategoriaPush.objects.filter(
            usuario_id=usuario.pk, categoria=categoria
        ).only("activo").first()
    except Exception:
        return True
    if pref is None:
        return True
    return bool(pref.activo)
