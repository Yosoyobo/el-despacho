"""Endpoints DRF de El Site — JSON para integraciones futuras (Grafana,
scripts externos, n8n). UI HTML vive en apps.el_site.

GET  /api/site                   → snapshot completo
POST /api/site/probar/<plat>     → fuerza re-check de una plataforma
POST /api/site/probar-todas      → batería completa
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from lib.portavoz import emitir
from lib.portavoz_eventos import EventoPortavoz
from lib.site import almacen, caddy, contenedores, droplet, host, internos, postgres, redis_status
from lib.site.registry import PLATAFORMAS, chequear

from ..permissions import SoloSuperAdminOdueno

_PlatSerializer = inline_serializer(
    name="ChequeoPlataforma",
    fields={
        "estado": serializers.CharField(),
        "latencia_ms": serializers.IntegerField(required=False, allow_null=True),
        "mensaje_error": serializers.CharField(required=False, allow_null=True),
    },
)


class SiteSnapshot(APIView):
    permission_classes = [SoloSuperAdminOdueno]

    @extend_schema(
        summary="Snapshot completo de El Site",
        description="Infraestructura del Droplet, integraciones (cacheadas) y servicios internos.",
        tags=["site"],
        responses={200: inline_serializer(name="SiteSnapshotResp", fields={
            "infra": serializers.DictField(),
            "integraciones": serializers.DictField(),
            "internos": serializers.DictField(),
        })},
    )
    def get(self, request):
        return Response({
            "infra": {
                "host": host.snapshot(),
                "containers": contenedores.snapshot(),
                "droplet_local": droplet.info_local(),
                "droplet_remoto": droplet.info_remota(),
                "postgres": postgres.detalles(),
                "redis": redis_status.detalles(),
                "caddy": caddy.snapshot(),
            },
            "integraciones": almacen.ultimo_por_plataforma(),
            "internos": internos.snapshot(),
        })


class SiteProbarPlataforma(APIView):
    permission_classes = [SoloSuperAdminOdueno]

    @extend_schema(
        summary="Re-chequea una plataforma",
        description="Corre el chequeo en vivo, guarda en `site_chequeo`, emite `site.integracion_fallo` si falla.",
        tags=["site"],
        responses={200: _PlatSerializer},
    )
    def post(self, request, plataforma: str):
        if plataforma not in PLATAFORMAS:
            return Response({"detail": f"plataforma desconocida: {plataforma}"}, status=status.HTTP_404_NOT_FOUND)
        res = chequear(plataforma)
        almacen.guardar(
            plataforma=plataforma,
            estado=res.get("estado", "error"),
            latencia_ms=res.get("latencia_ms"),
            mensaje_error=res.get("mensaje_error"),
            origen="manual",
            actor_email=request.user.email,
        )
        if res.get("estado") == "error":
            emitir(EventoPortavoz(
                tipo="site.integracion_fallo",
                actor_id=request.user.pk,
                actor_email=request.user.email,
                payload={
                    "plataforma": plataforma,
                    "estado": "error",
                    "mensaje_error": (res.get("mensaje_error") or "")[:500],
                    "latencia_ms": res.get("latencia_ms"),
                    "origen": "manual",
                    "actor_email": request.user.email,
                },
            ))
        return Response({
            "estado": res.get("estado"),
            "latencia_ms": res.get("latencia_ms"),
            "mensaje_error": res.get("mensaje_error"),
        })


class SiteProbarTodas(APIView):
    permission_classes = [SoloSuperAdminOdueno]

    @extend_schema(
        summary="Re-chequea todas las plataformas",
        description="Corre la batería entera. Útil para uptime monitors externos.",
        tags=["site"],
        responses={200: inline_serializer(name="ProbarTodasResp", fields={
            "resumen": serializers.DictField(),
        })},
    )
    def post(self, request):
        resumen: dict = {}
        for plat in PLATAFORMAS:
            res = chequear(plat)
            almacen.guardar(
                plataforma=plat,
                estado=res.get("estado", "error"),
                latencia_ms=res.get("latencia_ms"),
                mensaje_error=res.get("mensaje_error"),
                origen="manual",
                actor_email=request.user.email,
            )
            if res.get("estado") == "error":
                emitir(EventoPortavoz(
                    tipo="site.integracion_fallo",
                    actor_id=request.user.pk,
                    actor_email=request.user.email,
                    payload={
                        "plataforma": plat,
                        "estado": "error",
                        "mensaje_error": (res.get("mensaje_error") or "")[:500],
                        "latencia_ms": res.get("latencia_ms"),
                        "origen": "manual",
                        "actor_email": request.user.email,
                    },
                ))
            resumen[plat] = {
                "estado": res.get("estado"),
                "latencia_ms": res.get("latencia_ms"),
                "mensaje_error": res.get("mensaje_error"),
            }
        return Response({"resumen": resumen})
