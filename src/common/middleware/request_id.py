from contextvars import ContextVar
from types import SimpleNamespace
from typing import Any

from common.http.response import resolve_request_id

REQUEST_ID_HEADER = "X-Request-Id"
REQUEST_ID_META_KEY = "HTTP_X_REQUEST_ID"

# 使用 ContextVar 持有“当前请求”上下文，便于日志过滤器读取
_request_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "request_context",
    default=None,
)


def get_request_context() -> dict[str, Any]:
    # 返回当前请求上下文（无请求时返回空字典，避免日志字段缺失）
    return _request_context.get() or {}


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1) 透传或生成 request_id
        request_id = resolve_request_id(request)
        # 2) 注入 request.state / META，确保各层读取方式一致
        _ensure_request_state(request, request_id)
        # 3) 保存到 ContextVar，供日志过滤器读取
        token = _request_context.set({"request": request, "request_id": request_id})
        try:
            response = self.get_response(request)
        finally:
            # 防止请求上下文泄漏到下一个请求
            _request_context.reset(token)

        # 对非统一壳响应也补齐 header
        if response is not None and not response.has_header(REQUEST_ID_HEADER):
            response[REQUEST_ID_HEADER] = request_id
        return response


def _ensure_request_state(request, request_id: str) -> None:
    # META 统一存储 request_id，便于下游中间件/日志读取
    if hasattr(request, "META"):
        request.META.setdefault(REQUEST_ID_META_KEY, request_id)
    # Django 原生 request 无 state，这里补一个轻量容器
    if not hasattr(request, "state"):
        request.state = SimpleNamespace()
    if getattr(request.state, "request_id", None) is None:
        request.state.request_id = request_id
