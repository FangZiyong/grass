from datetime import datetime, timezone
import uuid

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_http_methods


def _resolve_request_id(request) -> str:
    """Echo client provided X-Request-Id or generate a new one."""
    header_value = request.headers.get("X-Request-Id")
    return header_value or f"req_{uuid.uuid4().hex}"


@require_http_methods(["GET"])
def healthz(request):
    request_id = _resolve_request_id(request)
    payload = {
        "code": "OK",
        "message": "OK",
        "data": {
            "status": "ok",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
        "request_id": request_id,
    }
    response = JsonResponse(payload, status=200)
    response["X-Request-Id"] = request_id
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.v1.urls")),
    path("healthz", healthz, name="healthz"),
]
