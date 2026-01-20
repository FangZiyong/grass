from datetime import datetime, timezone

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view

from common.http.response import envelope_response, resolve_request_id


@api_view(["GET"])
@extend_schema(
    responses={
        200: inline_serializer(
            name="HealthzEnvelope",
            fields={
                "code": serializers.CharField(),
                "message": serializers.CharField(),
                "data": inline_serializer(
                    name="HealthzData",
                    fields={
                        "status": serializers.CharField(),
                        "ts": serializers.CharField(),
                    },
                ),
                "request_id": serializers.CharField(),
            },
        )
    },
    tags=["Misc"],
    summary="健康检查",
)
def healthz(request):
    resolve_request_id(request)
    payload = {
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return envelope_response(payload, request=request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.v1.urls")),
    path("healthz", healthz, name="healthz"),
]
