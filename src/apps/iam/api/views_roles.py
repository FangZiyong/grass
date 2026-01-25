"""
Role API Views

角色管理接口：
- GET /api/roles
- POST /api/roles
- PATCH /api/roles/{role_id}
- DELETE /api/roles/{role_id}

租户上下文统一从请求头 X-Tenant-Id 解析（TenantContextMiddleware 注入 request.tenant_id / request.tenant_user）。
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.iam.api.serializers_roles import (
    RoleCreateSerializer,
    RoleDeleteEnvelopeSerializer,
    RoleEnvelopeSerializer,
    RoleListEnvelopeSerializer,
    RoleListQuerySerializer,
    RoleSerializer,
    RoleUpdateSerializer,
)
from apps.iam.selectors import list_roles
from apps.iam.services import create_role, delete_role, update_role
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException
from common.http.pagination import DefaultPageNumberPagination
from common.http.response import envelope_response


def _require_tenant_id(request) -> int:
    tenant_id = getattr(request, "tenant_id", None)
    if not tenant_id:
        raise GrassAPIException(
            detail="缺少租户上下文",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )
    return int(tenant_id)


def _get_tenant_actor(request):
    tenant_user = getattr(request, "tenant_user", None)
    if tenant_user is None:
        raise GrassAPIException(
            detail="缺少租户上下文",
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
        )
    return tenant_user


class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: RoleListEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="RoleListError400",
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
                    name="RoleListError401",
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
                    name="RoleListError403",
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
        tags=["IAM"],
        summary="角色列表",
    )
    def get(self, request):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        if not actor.is_owner:
            raise GrassAPIException(
                detail="无权限执行该操作",
                status_code=403,
                code=ErrorCode.PERMISSION_DENIED,
            )

        query_serializer = RoleListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        search = query_serializer.validated_data.get("q")
        if search is not None:
            search = search.strip() or None
        status = query_serializer.validated_data.get("status")

        queryset = list_roles(tenant_id, search=search, status=status)
        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = RoleSerializer(page, many=True, context={"actor": actor})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=RoleCreateSerializer,
        responses={
            200: RoleEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="RoleCreateError400",
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
                    name="RoleCreateError401",
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
                    name="RoleCreateError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="RoleCreateError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="冲突",
            ),
        },
        tags=["IAM"],
        summary="创建角色",
    )
    def post(self, request):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = create_role(tenant_id=tenant_id, actor=actor, **serializer.validated_data)
        return envelope_response(
            data={"role": RoleSerializer(role).data},
            request=request,
        )


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RoleUpdateSerializer,
        responses={
            200: RoleEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="RoleUpdateError400",
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
                    name="RoleUpdateError401",
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
                    name="RoleUpdateError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="RoleUpdateError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="RoleUpdateError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="冲突",
            ),
        },
        tags=["IAM"],
        summary="更新角色",
    )
    def patch(self, request, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = update_role(
            tenant_id=tenant_id,
            role_id=role_id,
            actor=actor,
            **serializer.validated_data,
        )
        return envelope_response(
            data={"role": RoleSerializer(role).data},
            request=request,
        )

    @extend_schema(
        responses={
            200: RoleDeleteEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="RoleDeleteError401",
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
                    name="RoleDeleteError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="RoleDeleteError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="RoleDeleteError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色被引用或不可删除",
            ),
        },
        tags=["IAM"],
        summary="删除角色",
    )
    def delete(self, request, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        delete_role(tenant_id=tenant_id, role_id=role_id, actor=actor)
        return envelope_response(data={"deleted": True}, request=request)
