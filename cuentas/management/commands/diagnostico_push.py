"""Diagnóstico de por qué (no) llegan los push de El Interfón / Novedades.

Reporte de Oscar: "las push de novedades no me llegan". Sin acceso a la DB de
prod, este comando responde las 4 preguntas que determinan si un push sale:

  1. ¿VAPID configurado en Los Ajustes? (sin esto NADA sale)
  2. ¿Quién tiene al menos un dispositivo suscrito y activo? (sin suscripción
     activa, su push queda en 'sin_suscripciones' — el caso típico en iPhone:
     hay que INSTALAR la PWA a la pantalla de inicio y permitir notificaciones).
  3. ¿Quién silenció la categoría 'novedades'?
  4. Desglose de las últimas entregas de la categoría 'novedades'.

Uso:
    python manage.py diagnostico_push
    python manage.py diagnostico_push --categoria novedades
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Diagnostica el estado de los push (VAPID, suscripciones, categoría)."

    def add_arguments(self, parser):
        parser.add_argument("--categoria", default="novedades",
                            help="Categoría a auditar (default: novedades).")

    def handle(self, *args, **opts):
        from cuentas.models.usuario import Usuario
        from interfono.models import InterfonoEntrega, InterfonoSuscripcion
        from interfono.models.preferencia import PreferenciaCategoriaPush
        from lib.interfono import InterfonoConfig

        cat = opts["categoria"]
        w = self.stdout.write
        ok = self.style.SUCCESS
        warn = self.style.WARNING

        w("\n=== 1. VAPID ===")
        configurado = InterfonoConfig.esta_configurado()
        w(f"  pública:  {'sí' if InterfonoConfig.vapid_public_key() else 'NO'}")
        w(f"  privada:  {'sí' if InterfonoConfig.vapid_private_key() else 'NO'}")
        w(f"  email:    {InterfonoConfig.vapid_email()}")
        w(ok("  → VAPID configurado: el push PUEDE salir.") if configurado
          else warn("  → VAPID NO configurado: NINGÚN push sale. Configúralo en /ajustes/."))

        w("\n=== 2. Suscripciones (dispositivos) ===")
        activos = Usuario.objects.filter(is_active=True)
        con_sub_ids = set(
            InterfonoSuscripcion.objects.filter(activa=True)
            .values_list("usuario_id", flat=True))
        con, sin = [], []
        for u in activos:
            (con if u.pk in con_sub_ids else sin).append(u)
        w(f"  usuarios activos: {activos.count()}")
        w(f"  con ≥1 dispositivo suscrito: {len(con)}")
        if sin:
            w(warn("  SIN dispositivo (no recibirán push):"))
            for u in sin:
                w(f"    · {u.email} ({u.nombre_completo})")
            w("  (En iPhone: instalar la PWA a la pantalla de inicio y permitir "
              "notificaciones crea la suscripción.)")

        w(f"\n=== 3. Categoría '{cat}' silenciada ===")
        silenciados = (PreferenciaCategoriaPush.objects
                       .filter(categoria=cat, activo=False)
                       .select_related("usuario"))
        if silenciados:
            for p in silenciados:
                w(warn(f"  · {p.usuario.email} silenció '{cat}'"))
        else:
            w("  nadie la silenció (default: activa).")

        w(f"\n=== 4. Últimas entregas de '{cat}' ===")
        entregas = InterfonoEntrega.objects.filter(categoria=cat).order_by("-enviado_en")[:200]
        total = entregas.count()
        if not total:
            w(warn(f"  0 entregas registradas de '{cat}'. ¿Corrió 'anunciar_novedades'? "
                   "¿Hay un bloque '## Novedades' nuevo en el manual desde el último deploy?"))
        else:
            conteo = Counter(e.estado_despacho or "(vacío)" for e in entregas)
            for estado, n in sorted(conteo.items()):
                w(f"  {estado}: {n}")
            ultima = entregas[0]
            w(f"  última: '{ultima.titulo[:50]}' · {ultima.enviado_en:%Y-%m-%d %H:%M}")
        w("")
