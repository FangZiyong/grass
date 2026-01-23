"""
Tenant API Views

根据 tech.md §4.7.3 和 architecture.md：
- GET /api/tenants：租户列表（T2.2任务实现）
- POST /api/tenants/switch：切换租户（T2.3任务实现）

注意：T0.5任务主要关注中间件，API接口的具体实现在T2.2和T2.3任务中完成。
这里先创建基础结构。
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from apps.accounts.selectors import get_user_by_id
from apps.tenants.api.serializers import (
    TenantBriefSerializer,
    TenantListEnvelopeSerializer,
    TenantSwitchEnvelopeSerializer,
    TenantSwitchResponseSerializer,
    TenantSwitchSerializer,
)
from apps.tenants.models.tenant import TenantStatus
from apps.tenants.selectors import list_user_tenants
from apps.tenants.services import switch_tenant
from common.errors.exceptions import GrassAPIException
from common.http.pagination import DefaultPageNumberPagination
from common.http.response import envelope_response


@extend_schema(
    responses={
        200: TenantListEnvelopeSerializer,
        401: OpenApiResponse(
            response=inline_serializer(
                name="TenantListError401",
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
                name="TenantListError403",
                fields={
                    "code": serializers.CharField(),
                    "message": serializers.CharField(),
                    "data": serializers.JSONField(required=False),
                    "request_id": serializers.CharField(),
                },
            ),
            description="无权限",
        ),
    },
    tags=["Tenants"],
    summary="获取可访问租户列表",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tenant_list_view(request: Request):
    """
    获取当前用户可访问的租户列表
    
    根据 tech.md §4.6.2 和 T2.2任务：
    - 返回用户所属的 ACTIVE 租户列表
    - 支持 q 搜索（租户 code/name）
    - 返回最近租户标识（基于 user.last_tenant_id）
    """
    user_id = request.user.user_id if hasattr(request.user, "user_id") else request.user.pk

    user = get_user_by_id(user_id)
    if user is None:
        raise GrassAPIException(
            detail="User not found.",
            status_code=500,
            code="DATA_INTEGRITY_ERROR",
        )
    
    search = request.query_params.get("q")
    if search is not None:
        search = search.strip()
    if not search:
        search = None

    tenants = list_user_tenants(user_id, status=TenantStatus.ACTIVE, search=search)

    paginator = DefaultPageNumberPagination()
    paginator.page_size = 50
    page = paginator.paginate_queryset(tenants, request)

    serializer = TenantBriefSerializer(
        page,
        many=True,
        context={"recent_tenant_id": user.last_tenant_id},
    )

    return paginator.get_paginated_response(serializer.data)


@extend_schema(
    request=TenantSwitchSerializer,
    responses={
        200: TenantSwitchEnvelopeSerializer,
        400: OpenApiResponse(
            response=inline_serializer(
                name="TenantSwitchError400",
                fields={
                    "code": serializers.CharField(),
                    "message": serializers.CharField(),
                    "data": serializers.JSONField(required=False),
                    "request_id": serializers.CharField(),
                },
            ),
            description="参数校验失败",
        ),
        401: OpenApiResponse(
            response=inline_serializer(
                name="TenantSwitchError401",
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
                name="TenantSwitchError403",
                fields={
                    "code": serializers.CharField(),
                    "message": serializers.CharField(),
                    "data": serializers.JSONField(required=False),
                    "request_id": serializers.CharField(),
                },
            ),
            description="租户停用或无权限",
        ),
        404: OpenApiResponse(
            response=inline_serializer(
                name="TenantSwitchError404",
                fields={
                    "code": serializers.CharField(),
                    "message": serializers.CharField(),
                    "data": serializers.JSONField(required=False),
                    "request_id": serializers.CharField(),
                },
            ),
            description="租户不存在",
        ),
    },
    tags=["Tenants"],
    summary="切换租户",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tenant_switch_view(request: Request):
    """
    切换租户上下文
    
    根据 tech.md §4.7.3 和 T2.3任务：
    - 校验租户存在且为 ACTIVE
    - 校验用户属于该租户
    - 更新 last_tenant_id（T1.5任务实现）
    
    注意：完整实现在T2.3任务中完成，这里先提供基础实现。
    """
    serializer = TenantSwitchSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user_id = request.user.user_id if hasattr(request.user, "user_id") else request.user.pk
    tenant_id = serializer.validated_data["tenant_id"]
    
    # 调用服务层切换租户
    result = switch_tenant(user_id, tenant_id)
    
    response_serializer = TenantSwitchResponseSerializer(data=result)
    response_serializer.is_valid(raise_exception=True)
    
    return envelope_response(
        data=response_serializer.validated_data,
        request=request,
    )

