from __future__ import annotations

from django.conf import settings
from django.db import models


class InterfonoEntrega(models.Model):
    """Una fila por (usuario, push) — historial orientado al destinatario.

    Se persiste SIEMPRE que `lib.interfono.enviar_a_usuario()` se invoque,
    incluso si la categoría está desactivada o si VAPID no está configurado.
    Eso permite que el usuario, al activar después una categoría, vea las
    que se perdió, y nos da auditoría completa.

    Los campos `titulo`/`cuerpo`/`url` son redundantes con el `InterfonoEnvio`
    agregado pero los duplicamos aquí a propósito: las queries de la UI del
    perfil son siempre per-usuario y no necesitan join.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entregas_interfono",
    )

    titulo = models.CharField(max_length=200)
    cuerpo = models.TextField()
    url = models.CharField(max_length=500, blank=True, default="")
    categoria = models.CharField(max_length=40, blank=True, default="")
    tag = models.CharField(max_length=100, blank=True, default="")

    enviado_en = models.DateTimeField(auto_now_add=True)
    clickeado_en = models.DateTimeField(null=True, blank=True)
    visto_en = models.DateTimeField(null=True, blank=True)

    origen_modulo = models.CharField(max_length=40, blank=True, default="")
    origen_id = models.BigIntegerField(null=True, blank=True)

    # Estado del intento de despacho al navegador (informativo).
    # 'entregada' | 'silenciada_categoria' | 'no_configurado' | 'sin_suscripciones' | 'fallida'
    estado_despacho = models.CharField(max_length=30, blank=True, default="")

    class Meta:
        db_table = "interfono_entrega"
        ordering = ["-enviado_en"]
        indexes = [
            models.Index(fields=["usuario", "-enviado_en"], name="entrega_user_fecha_idx"),
            models.Index(fields=["usuario", "clickeado_en"], name="entrega_user_click_idx"),
            models.Index(fields=["categoria", "-enviado_en"], name="entrega_cat_fecha_idx"),
        ]

    def __str__(self) -> str:
        return f"entrega#{self.pk} u={self.usuario_id} '{self.titulo[:30]}'"
