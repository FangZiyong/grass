from datetime import datetime, timezone

from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view

from common.http.response import envelope_response, resolve_request_id


@api_view(["GET"])
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
