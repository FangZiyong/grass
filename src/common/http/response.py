import uuid
from typing import Any, Optional, Type

from rest_framework import serializers, status
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


class EnvelopeSerializer(serializers.Serializer):
    """
    统一响应壳序列化器（用于 OpenAPI 文档生成）
    
    所有 API 响应都使用统一的结构：
    {
        "code": str,
        "message": str,
        "data": Any,
        "request_id": str
    }
    """
    
    code = serializers.CharField(help_text="响应码")
    message = serializers.CharField(help_text="响应消息")
    data = serializers.JSONField(help_text="响应数据", required=False, allow_null=True)
    request_id = serializers.CharField(help_text="请求ID")


def create_envelope_serializer(data_serializer: Type[serializers.Serializer] | None = None) -> Type[serializers.Serializer]:
    """
    创建带特定 data 类型的统一响应壳序列化器（用于 OpenAPI 文档生成）
    
    Args:
        data_serializer: data 字段的序列化器类，如果为 None 则使用 JSONField
    
    Returns:
        统一响应壳序列化器类
    
    Example:
        # 使用自定义 data 序列化器
        MoveNodeDataSerializer = create_envelope_serializer(MoveNodeResponseDataSerializer)
        
        # 使用默认 JSONField（适用于 data 结构简单或动态的场景）
        SimpleEnvelopeSerializer = create_envelope_serializer()
    """
    if data_serializer is None:
        data_field = serializers.JSONField(help_text="响应数据", required=False, allow_null=True)
    else:
        data_field = data_serializer(help_text="响应数据")
    
    class_name = f"EnvelopeSerializer_{id(data_serializer) if data_serializer else 'default'}"
    
    class DynamicEnvelopeSerializer(serializers.Serializer):
        """动态生成的统一响应壳序列化器"""
        
        code = serializers.CharField(help_text="响应码")
        message = serializers.CharField(help_text="响应消息")
        data = data_field
        request_id = serializers.CharField(help_text="请求ID")
    
    DynamicEnvelopeSerializer.__name__ = class_name
    return DynamicEnvelopeSerializer
