"""
IAM 权限 API Views

实现 T3.5 角色资源授权接口：
- GET /api/roles/{role_id}/resource-permissions
- PUT /api/roles/{role_id}/resource-permissions
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.iam.api.serializers_permissions import (
    PermissionPanelEnvelopeSerializer,
    PermissionPanelQuerySerializer,
    RoleResourcePermissionsEnvelopeSerializer,
    SaveRoleResourcePermissionsEnvelopeSerializer,
    SaveRoleResourcePermissionsRequestSerializer,
)
from apps.iam.models.grants import PermissionLevel
from apps.iam.selectors import (
    get_role_by_id,
    list_role_grants_by_node,
    list_role_permissions,
    list_user_role_ids,
)
from apps.iam.services import save_role_resource_permissions
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException
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


def _ensure_role_grant_manage_permission(actor) -> None:
    if not actor.is_owner:
        raise GrassAPIException(
            detail="无权限执行该操作",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )


def _ensure_grant_view_permission(actor) -> None:
    if not actor.is_owner:
        raise GrassAPIException(
            detail="无权限执行该操作",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )


_PERMISSION_RANK = {
    PermissionLevel.NONE: 0,
    PermissionLevel.VIEW: 1,
    PermissionLevel.EDIT: 2,
    PermissionLevel.MANAGE: 3,
}


class RoleResourcePermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: RoleResourcePermissionsEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="RoleResourcePermissionsError400",
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
                    name="RoleResourcePermissionsError401",
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
                    name="RoleResourcePermissionsError403",
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
                    name="RoleResourcePermissionsError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色不存在",
            ),
        },
        tags=["IAM"],
        summary="查询角色资源授权",
    )
    def get(self, request, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        _ensure_role_grant_manage_permission(actor)

        role = get_role_by_id(tenant_id, role_id)
        if role is None:
            raise GrassAPIException(
                detail="角色不存在",
                status_code=404,
                code="ROLE_NOT_FOUND",
            )

        queryset = list_role_permissions(tenant_id=tenant_id, role_id=role_id)
        items = [
            {
                "grant_id": perm.role_permission_id,
                "resource_tree_node_id": perm.resource_tree_node_id,
                "resource_type": perm.resource_type,
                "permission_level": perm.permission,
                "is_inherited": False,
            }
            for perm in queryset
        ]
        return envelope_response(data={"items": items}, request=request)

    @extend_schema(
        request=SaveRoleResourcePermissionsRequestSerializer,
        responses={
            200: SaveRoleResourcePermissionsEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="SaveRoleResourcePermissionsError400",
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
                    name="SaveRoleResourcePermissionsError401",
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
                    name="SaveRoleResourcePermissionsError403",
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
                    name="SaveRoleResourcePermissionsError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色不存在",
            ),
        },
        tags=["IAM"],
        summary="保存角色资源授权",
    )
    def put(self, request, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        _ensure_role_grant_manage_permission(actor)

        serializer = SaveRoleResourcePermissionsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = save_role_resource_permissions(
            tenant_id=tenant_id,
            role_id=role_id,
            items=serializer.validated_data["items"],
            actor=actor,
        )
        return envelope_response(data={"updated": updated}, request=request)


class ResourcePermissionPanelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: PermissionPanelEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="PermissionPanelError400",
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
                    name="PermissionPanelError401",
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
                    name="PermissionPanelError403",
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
        summary="权限面板数据",
    )
    def get(self, request, resource_node_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        _ensure_grant_view_permission(actor)

        serializer = PermissionPanelQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        resource_type = serializer.validated_data["resource_type"]

        role_grants_qs = list_role_grants_by_node(
            tenant_id=tenant_id,
            resource_tree_node_id=resource_node_id,
            resource_type=resource_type,
        )
        role_grants = [
            {
                "grant_id": perm.role_permission_id,
                "role_id": perm.role_id,
                "role_name": perm.role.name,
                "permission_level": perm.permission,
            }
            for perm in role_grants_qs
        ]

        user_role_ids = list_user_role_ids(
            tenant_id=tenant_id,
            tenant_user_id=actor.tenant_user_id,
        )
        if user_role_ids:
            user_perms = role_grants_qs.filter(role_id__in=user_role_ids)
            max_level = PermissionLevel.NONE
            max_rank = _PERMISSION_RANK[max_level]
            for perm in user_perms:
                rank = _PERMISSION_RANK.get(perm.permission, 0)
                if rank > max_rank:
                    max_rank = rank
                    max_level = perm.permission
            my_effective_permission = max_level
        else:
            my_effective_permission = PermissionLevel.NONE

        can_manage = actor.is_owner or my_effective_permission == PermissionLevel.MANAGE
        return envelope_response(
            data={
                "resource_node_id": resource_node_id,
                "role_grants": role_grants,
                "my_effective_permission": my_effective_permission,
                "can_manage": can_manage,
            },
            request=request,
        )

