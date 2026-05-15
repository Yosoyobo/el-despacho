"""Endpoint mínimo de información del API — sirve para validar que DRF y
drf-spectacular están bien cableados antes de que lleguen endpoints reales en
S2a.2 (El Site) y S2b (webhooks Stripe/MercadoPago)."""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import SoloSuperAdmin


class InfoApiView(APIView):
    """Información de versión y estado del API. Útil como smoke-test del
    Inventario de Endpoints."""

    permission_classes = [SoloSuperAdmin]

    @extend_schema(
        summary="Información del API",
        description="Versión actual del API y endpoints publicados al momento.",
        responses={200: inline_serializer(
            name="ApiInfo",
            fields={
                "version": serializers.CharField(),
                "sprint": serializers.CharField(),
                "modulos_publicados": serializers.ListField(child=serializers.CharField()),
            },
        )},
        tags=["meta"],
    )
    def get(self, request):
        return Response({
            "version": "0.1.0-s2a",
            "sprint": "S2a.1",
            "modulos_publicados": [
                "meta/info",
            ],
        })
