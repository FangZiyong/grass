"""
IAM 权限 API Views

角色资源授权接口：
- GET /api/roles/{role_id}/resource-permissions
- PUT /api/roles/{role_id}/resource-permissions

授权管理接口：
- POST /api/permissions/grants
- DELETE /api/permissions/grants/{grant_id}
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.iam.api.serializers_permissions import (
    PermissionPanelEnvelopeSerializer,
    PermissionPanelQuerySerializer,
    RevokeGrantEnvelopeSerializer,
    RoleResourcePermissionsEnvelopeSerializer,
    SaveRoleResourcePermissionsEnvelopeSerializer,
    SaveRoleResourcePermissionsRequestSerializer,
    UpsertGrantEnvelopeSerializer,
    UpsertGrantRequestSerializer,
)
from apps.iam.models.grants import PermissionLevel
from apps.iam.selectors import (
    get_role_by_id,
    list_role_grants_by_node,
    list_role_permissions,
    list_user_role_ids,
)
from apps.iam.services import revoke_grant, save_role_resource_permissions, upsert_grant
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


class GrantsView(APIView):
    """
    授权管理接口

    POST /api/permissions/grants - 创建/更新授权

    功能说明：
    - 为指定角色授予对某资源节点的权限（upsert 语义）
    - 若授权已存在，则更新权限等级
    - 若 permission_level=NONE，则删除该授权

    权限要求：仅 Owner 可操作

    错误码：
    - BAD_REQUEST(400): 参数校验失败
    - UNAUTHENTICATED(401): 未登录
    - PERMISSION_DENIED(403): 非 Owner 无权限
    - ROLE_NOT_FOUND(404): 角色不存在
    - RESOURCE_NODE_NOT_FOUND(404): 资源节点不存在
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=UpsertGrantRequestSerializer,
        responses={
            200: UpsertGrantEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="UpsertGrantError400",
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
                    name="UpsertGrantError401",
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
                    name="UpsertGrantError403",
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
                    name="UpsertGrantError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="角色或资源节点不存在",
            ),
        },
        tags=["IAM"],
        summary="创建/更新授权",
    )
    def post(self, request):
        """
        创建或更新授权记录

        请求体示例：
        {
            "scope": "FLOW",
            "resource_tree_node_id": 123,
            "role_id": 456,
            "permission_level": "EDIT"
        }

        响应示例：
        {
            "code": "OK",
            "message": "success",
            "data": {"grant_id": 789},
            "request_id": "..."
        }
        """
        # 1. 获取租户上下文和操作人
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        # 2. 校验请求参数
        serializer = UpsertGrantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 3. 执行 upsert 操作
        grant_id, _ = upsert_grant(
            tenant_id=tenant_id,
            role_id=data["role_id"],
            resource_type=data["resource_type"],
            resource_tree_node_id=data["resource_tree_node_id"],
            permission_level=data["permission_level"],
            actor=actor,
        )
        return envelope_response(data={"grant_id": grant_id}, request=request)


class GrantDetailView(APIView):
    """
    授权详情接口

    DELETE /api/permissions/grants/{grant_id} - 撤销授权

    功能说明：
    - 根据 grant_id 删除指定的授权记录
    - 删除后，对应角色将失去该资源节点的权限

    权限要求：仅 Owner 可操作

    错误码：
    - UNAUTHENTICATED(401): 未登录
    - PERMISSION_DENIED(403): 非 Owner 无权限
    - GRANT_NOT_FOUND(404): 授权记录不存在
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: RevokeGrantEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="RevokeGrantError401",
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
                    name="RevokeGrantError403",
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
                    name="RevokeGrantError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="授权记录不存在",
            ),
        },
        tags=["IAM"],
        summary="撤销授权",
    )
    def delete(self, request, grant_id: int):
        """
        撤销（删除）授权记录

        路径参数：
        - grant_id: 授权记录 ID（即 role_permission_id）

        响应示例：
        {
            "code": "OK",
            "message": "success",
            "data": {"deleted": true},
            "request_id": "..."
        }
        """
        # 1. 获取租户上下文和操作人
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        # 2. 执行撤销操作
        deleted = revoke_grant(
            tenant_id=tenant_id,
            grant_id=grant_id,
            actor=actor,
        )
        return envelope_response(data={"deleted": deleted}, request=request)

