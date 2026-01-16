import uuid
from typing import Any, Optional

from rest_framework import status
from rest_framework.response import Response

from common.errors.codes import ErrorCode


def resolve_request_id(request=None) -> str:
    """
    提取或生成 request_id，优先使用请求头 X-Request-Id，并缓存到 request 上。
    """
    if request is None:
        return f"req_{uuid.uuid4().hex}"

    cached = getattr(request, "request_id", None)
    if cached:
        return cached

    header_value: Optional[str] = None
    if hasattr(request, "headers"):
        header_value = request.headers.get("X-Request-Id")
    if not header_value and hasattr(request, "META"):
        header_value = request.META.get("HTTP_X_REQUEST_ID")

    request_id = header_value or f"req_{uuid.uuid4().hex}"
    setattr(request, "request_id", request_id)
    return request_id


def envelope_response(
    data: Any = None,
    *,
    code: ErrorCode | str = ErrorCode.OK,
    message: str = "OK",
    status_code: int = status.HTTP_200_OK,
    request=None,
) -> Response:
    """
    构造统一壳响应。
    """
    request_id = resolve_request_id(request)
    payload = {
        "code": str(code),
        "message": message or "",
        "data": data,
        "request_id": request_id,
    }
    response = Response(payload, status=status_code)
    response["X-Request-Id"] = request_id
    return response
