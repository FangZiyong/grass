"""
成员-角色绑定 API Views

成员绑定角色接口：
- POST /api/users/{tenant_user_id}/roles
- DELETE /api/users/{tenant_user_id}/roles/{role_id}
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.accounts.models.users import GlobalUser
from apps.iam.api.serializers_membership import (
    MemberRoleBindEnvelopeSerializer,
    MemberRoleBindRequestSerializer,
    MemberRolesEnvelopeSerializer,
    MemberRoleUnbindEnvelopeSerializer,
    OwnerSetEnvelopeSerializer,
    OwnerUnsetEnvelopeSerializer,
    RoleSummarySerializer,
    RoleUsersListEnvelopeSerializer,
    TenantUserSummarySerializer,
)
from apps.iam.models.roles import Role
from apps.iam.selectors import get_role_by_id
from apps.iam.services import (
    bind_roles_to_user,
    set_tenant_user_owner,
    unbind_role_from_user,
    unset_tenant_user_owner,
)
from apps.tenants.models.tenant_user import TenantUser
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


class MemberRoleBindView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: MemberRolesEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="MemberRolesError401",
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
                    name="MemberRolesError403",
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
                    name="MemberRolesError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="成员不存在",
            ),
        },
        tags=["IAM"],
        summary="查询成员角色",
    )
    def get(self, request, tenant_user_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        if not actor.is_owner:
            raise GrassAPIException(
                detail="无权限执行该操作",
                status_code=403,
                code=ErrorCode.PERMISSION_DENIED,
            )

        tenant_user = TenantUser.objects.filter(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
        ).first()
        if tenant_user is None:
            raise GrassAPIException(
                detail="成员不存在",
                status_code=404,
                code="TENANT_USER_NOT_FOUND",
            )

        roles = (
            Role.objects.filter(
                tenant_id=tenant_id,
                user_bindings__tenant_user_id=tenant_user_id,
            )
            .distinct()
            .order_by("-created_at", "-role_id")
        )
        serializer = RoleSummarySerializer(roles, many=True)
        return envelope_response(data={"roles": serializer.data}, request=request)

    @extend_schema(
        request=MemberRoleBindRequestSerializer,
        responses={
            200: MemberRoleBindEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="MemberRoleBindError400",
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
                    name="MemberRoleBindError401",
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
                    name="MemberRoleBindError403",
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
                    name="MemberRoleBindError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="成员或角色不存在",
            ),
        },
        tags=["IAM"],
        summary="绑定成员角色",
    )
    def post(self, request, tenant_user_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        serializer = MemberRoleBindRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_ids = bind_roles_to_user(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            role_ids=serializer.validated_data["role_ids"],
            actor=actor,
        )
        return envelope_response(data={"role_ids": role_ids}, request=request)


class MemberRoleUnbindView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: MemberRoleUnbindEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="MemberRoleUnbindError401",
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
                    name="MemberRoleUnbindError403",
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
                    name="MemberRoleUnbindError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="成员或角色不存在",
            ),
        },
        tags=["IAM"],
        summary="解绑成员角色",
    )
    def delete(self, request, tenant_user_id: int, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        deleted = unbind_role_from_user(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            role_id=role_id,
            actor=actor,
        )
        return envelope_response(data={"deleted": deleted}, request=request)


class RoleUsersListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: RoleUsersListEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="RoleUsersError401",
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
                    name="RoleUsersError403",
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
                    name="RoleUsersError404",
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
        summary="查询角色成员",
    )
    def get(self, request, role_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)
        if not actor.is_owner:
            raise GrassAPIException(
                detail="无权限执行该操作",
                status_code=403,
                code=ErrorCode.PERMISSION_DENIED,
            )

        role = get_role_by_id(tenant_id, role_id)
        if role is None:
            raise GrassAPIException(
                detail="角色不存在",
                status_code=404,
                code="ROLE_NOT_FOUND",
            )

        queryset = TenantUser.objects.filter(
            tenant_id=tenant_id,
            role_bindings__role_id=role.role_id,
        ).order_by("-created_at", "-tenant_user_id")

        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)

        user_ids = [item.user_id for item in page]
        user_map = {
            user.user_id: user
            for user in GlobalUser.objects.filter(user_id__in=user_ids)
        }

        items = []
        for tenant_user in page:
            user = user_map.get(tenant_user.user_id)
            items.append(
                {
                    "tenant_user_id": tenant_user.tenant_user_id,
                    "user_id": tenant_user.user_id,
                    "email": user.email if user else "",
                    "display_name": user.display_name if user else None,
                    "status": tenant_user.status,
                    "created_at": tenant_user.created_at,
                }
            )

        serializer = TenantUserSummarySerializer(items, many=True)
        return paginator.get_paginated_response(serializer.data)


class MemberOwnerView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OwnerSetEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="OwnerSetError401",
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
                    name="OwnerSetError403",
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
                    name="OwnerSetError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="成员不存在",
            ),
        },
        tags=["IAM"],
        summary="设为 Owner",
    )
    def post(self, request, tenant_user_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        is_owner = set_tenant_user_owner(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            actor=actor,
        )
        return envelope_response(data={"is_owner": is_owner}, request=request)

    @extend_schema(
        responses={
            200: OwnerUnsetEnvelopeSerializer,
            401: OpenApiResponse(
                response=inline_serializer(
                    name="OwnerUnsetError401",
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
                    name="OwnerUnsetError403",
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
                    name="OwnerUnsetError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="成员不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="OwnerUnsetError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="至少保留 1 名 Owner",
            ),
        },
        tags=["IAM"],
        summary="取消 Owner",
    )
    def delete(self, request, tenant_user_id: int):
        tenant_id = _require_tenant_id(request)
        actor = _get_tenant_actor(request)

        is_owner = unset_tenant_user_owner(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            actor=actor,
        )
        return envelope_response(data={"is_owner": is_owner}, request=request)

