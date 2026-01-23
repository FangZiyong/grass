"""
我的信息 API View

- GET /api/me
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.accounts.api.serializers import MeResponseEnvelopeSerializer
from apps.accounts.models.users import GlobalUserStatus
from apps.accounts.selectors import get_user_by_id
from apps.tenants.models.tenant import TenantStatus
from apps.tenants.models.tenant_user import TenantUserStatus
from apps.tenants.selectors import get_tenant_by_id, get_tenant_user, list_user_tenants
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException
from common.http.response import envelope_response


class MeView(APIView):
    """
    获取当前用户信息与租户上下文
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: MeResponseEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="MeError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="MeError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="用户被禁用",
            ),
            500: OpenApiResponse(
                response=inline_serializer(
                    name="MeError500",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="数据异常",
            ),
        },
        tags=["Auth"],
        summary="获取当前用户信息",
    )
    def get(self, request):
        user_id = request.user.user_id
        user = get_user_by_id(user_id)
        if user is None:
            raise GrassAPIException(
                detail="User not found.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="DATA_INTEGRITY_ERROR",
            )

        if user.status != GlobalUserStatus.ACTIVE:
            raise GrassAPIException(
                detail="User is disabled.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="AUTH_USER_DISABLED",
            )

        payload = {
            "user": {
                "user_id": user.user_id,
                "login_name": user.login_name,
                "display_name": user.display_name,
                "email": user.email,
                "is_platform_admin": user.is_platform_admin,
                "status": user.status,
                "last_tenant_id": user.last_tenant_id,
            }
        }

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            header_value = request.headers.get("X-Tenant-Id") or request.META.get("HTTP_X_TENANT_ID")
            if header_value:
                try:
                    tenant_id = int(header_value)
                except (TypeError, ValueError):
                    raise GrassAPIException(
                        detail="X-Tenant-Id header must be an integer.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code=ErrorCode.BAD_REQUEST,
                    )

                tenant = get_tenant_by_id(tenant_id)
                if tenant is None:
                    raise GrassAPIException(
                        detail="Tenant not found.",
                        status_code=status.HTTP_404_NOT_FOUND,
                        code=ErrorCode.NOT_FOUND,
                    )
                if tenant.status != TenantStatus.ACTIVE:
                    raise GrassAPIException(
                        detail="Tenant is suspended.",
                        status_code=status.HTTP_403_FORBIDDEN,
                        code=ErrorCode.PERMISSION_DENIED,
                    )

                tenant_user = get_tenant_user(tenant_id, user_id)
                if tenant_user is None or tenant_user.status != TenantUserStatus.ACTIVE:
                    raise GrassAPIException(
                        detail="User is not allowed for this tenant.",
                        status_code=status.HTTP_403_FORBIDDEN,
                        code=ErrorCode.PERMISSION_DENIED,
                    )
            elif user.last_tenant_id:
                # 兼容前端未携带 X-Tenant-Id 的场景：若用户已记录最近租户，则尝试解析租户上下文。
                # 校验失败时不报错，仅不返回 tenant 字段（避免 /api/me 因租户异常而不可用）。
                tenant_candidate = get_tenant_by_id(user.last_tenant_id)
                if tenant_candidate is not None and tenant_candidate.status == TenantStatus.ACTIVE:
                    tenant_user = get_tenant_user(tenant_candidate.tenant_id, user_id)
                    if tenant_user is not None and tenant_user.status == TenantUserStatus.ACTIVE:
                        tenant = tenant_candidate
            else:
                # 若用户只属于一个可用租户，则可在未传 header 时自动返回该租户上下文。
                active_tenants = list(list_user_tenants(user_id, status=TenantStatus.ACTIVE))
                if len(active_tenants) == 1:
                    tenant = active_tenants[0]
        if tenant is not None:
            payload["tenant"] = {
                "tenant_id": tenant.tenant_id,
                "code": tenant.code,
                "name": tenant.name,
                "plan": tenant.plan,
            }

        return envelope_response(data=payload, request=request)
