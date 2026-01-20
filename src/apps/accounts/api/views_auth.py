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
        request=LoginSerializer,
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
        auth_service.set_refresh_cookie(
            response,
            refresh_token=result.refresh_token,
            expires_at=result.refresh_expires_at,
        )
        return response
