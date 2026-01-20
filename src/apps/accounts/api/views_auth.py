"""
Auth API Views

- POST /api/auth/login
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.accounts.api.serializers import (
    LoginResponseEnvelopeSerializer,
    LoginSerializer,
    LogoutResponseEnvelopeSerializer,
    RefreshResponseEnvelopeSerializer,
)
from apps.accounts.services import auth as auth_service
from common.errors.exceptions import GrassAPIException
from common.http.response import envelope_response


def _map_validation_error(exc: ValidationError) -> GrassAPIException:
    detail = getattr(exc, "detail", None)
    message = "Invalid request."
    if isinstance(detail, dict):
        first_value = next(iter(detail.values()), None)
        if isinstance(first_value, (list, tuple)) and first_value:
            message = str(first_value[0])
        elif first_value is not None:
            message = str(first_value)
    elif detail:
        message = str(detail)

    code = "VALIDATION_FORMAT"
    if _has_required_error(detail):
        code = "VALIDATION_REQUIRED"

    return GrassAPIException(
        detail=message,
        status_code=400,
        code=code,
        data=detail,
    )


def _has_required_error(detail) -> bool:
    if detail is None:
        return False
    if isinstance(detail, dict):
        return any(_has_required_error(value) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return any(_has_required_error(value) for value in detail)
    return "required" in str(detail).lower()


class LoginView(APIView):
    """
    用户登录
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "application/x-www-form-urlencoded": LoginSerializer,
            "multipart/form-data": LoginSerializer,
        },
        responses={
            200: LoginResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="LoginError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（VALIDATION_*）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="LoginError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="账号或密码错误",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="LoginError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="用户被禁用",
            ),
            429: OpenApiResponse(
                response=inline_serializer(
                    name="LoginError429",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="尝试次数过多",
            ),
        },
        tags=["Auth"],
        summary="用户登录",
    )
    def post(self, request):
        # 统一把表单/JSON 数据走 DRF 校验：
        # - 保证字段长度/必填规则一致
        # - 将 ValidationError 统一映射为 VALIDATION_* 错误码
        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            raise _map_validation_error(exc)

        result = auth_service.login(
            login_name=serializer.validated_data["login_name"],
            password=serializer.validated_data["password"],
            request=request,
        )
        response = envelope_response(data=result.payload, request=request)
        # 登录成功后下发 refresh cookie：
        # - HttpOnly，前端不可读
        # - 仅作为刷新 access token 的凭证
        auth_service.set_refresh_cookie(
            response,
            refresh_token=result.refresh_token,
            expires_at=result.refresh_expires_at,
        )
        return response


class RefreshView(APIView):
    """
    刷新 access token
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: RefreshResponseEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="RefreshError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="Refresh token 无效/过期/已撤销",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="RefreshError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="用户被禁用",
            ),
        },
        tags=["Auth"],
        summary="刷新 access token",
    )
    def post(self, request):
        # refresh 不依赖 body，直接使用 HttpOnly cookie：
        # - 兼容跨端/跨设备请求
        # - 避免 refresh token 暴露在 JS/日志中
        result = auth_service.refresh(request=request)
        response = envelope_response(data=result.payload, request=request)
        # 轮换策略生效时才更新 cookie：
        # - 防止每次刷新都触发 set-cookie（可配置关闭轮换）
        if result.refresh_token:
            auth_service.set_refresh_cookie(
                response,
                refresh_token=result.refresh_token,
                expires_at=result.refresh_expires_at,
            )
        return response


class LogoutView(APIView):
    """
    用户登出
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: LogoutResponseEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="LogoutError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="Refresh token 无效/缺失",
            ),
        },
        tags=["Auth"],
        summary="用户退出登录",
    )
    def post(self, request):
        auth_service.logout(request=request)
        response = envelope_response(data={}, request=request)
        auth_service.clear_refresh_cookie(response)
        return response
