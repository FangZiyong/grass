import logging

from common.middleware.request_id import get_request_context


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # 读取中间件写入的上下文（缺失时使用 "-" 占位）
        context = get_request_context()
        request = context.get("request")
        request_id = context.get("request_id")

        if not request_id and request is not None:
            request_id = getattr(request, "request_id", None)
            if not request_id and hasattr(request, "META"):
                request_id = request.META.get("HTTP_X_REQUEST_ID")

        # tenant_id 允许从 request.tenant_id 或 request.tenant.id 获取
        tenant_id = None
        if request is not None:
            tenant_id = getattr(request, "tenant_id", None)
            if tenant_id is None:
                tenant = getattr(request, "tenant", None)
                tenant_id = getattr(tenant, "id", None) if tenant is not None else None

        # user_id 优先取认证用户，否则尝试 request.user_id
        user_id = None
        if request is not None:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                user_id = getattr(user, "id", None) or getattr(user, "pk", None)
            if user_id is None:
                user_id = getattr(request, "user_id", None)

        record.request_id = request_id or "-"
        record.tenant_id = tenant_id or "-"
        record.user_id = user_id or "-"
        return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": RequestContextFilter,
        }
    },
    "formatters": {
        "standard": {
            "format": (
                # 结构化输出：便于后续采集与检索
                "%(asctime)s %(levelname)s %(name)s "
                "request_id=%(request_id)s tenant_id=%(tenant_id)s "
                "user_id=%(user_id)s %(message)s"
            ),
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context"],
            "formatter": "standard",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
