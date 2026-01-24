"""
IAM 查询层（只读操作）
"""
from typing import Optional

from django.db.models import Q, QuerySet

from apps.iam.models.grants import RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role


def get_role_by_id(tenant_id: int, role_id: int) -> Optional[Role]:
    """
    获取指定租户内的角色。
    """
    try:
        return Role.objects.get(tenant_id=tenant_id, role_id=role_id)
    except Role.DoesNotExist:
        return None


def list_roles(
    tenant_id: int,
    *,
    search: Optional[str] = None,
    status: Optional[str] = None,
) -> QuerySet[Role]:
    """
    获取租户内角色列表（支持搜索与状态过滤）。
    """
    queryset = Role.objects.filter(tenant_id=tenant_id)

    if status:
        queryset = queryset.filter(status=status)

    if search:
        queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))

    return queryset.order_by("-created_at", "-role_id")


def list_role_permissions(tenant_id: int, role_id: int) -> QuerySet[RolePermission]:
    """
    获取指定角色的资源授权列表。
    """
    return (
        RolePermission.objects.filter(tenant_id=tenant_id, role_id=role_id)
        .order_by("resource_type", "resource_tree_node_id", "role_permission_id")
    )


def list_role_grants_by_node(
    *,
    tenant_id: int,
    resource_tree_node_id: int,
    resource_type: str,
) -> QuerySet[RolePermission]:
    """
    获取资源节点的角色授权列表。
    """
    return (
        RolePermission.objects.filter(
            tenant_id=tenant_id,
            resource_tree_node_id=resource_tree_node_id,
            resource_type=resource_type,
        )
        .select_related("role")
        .order_by("role_id", "role_permission_id")
    )


def list_user_role_ids(*, tenant_id: int, tenant_user_id: int) -> list[int]:
    """
    获取成员绑定的角色 ID 列表。
    """
    return list(
        TenantUserRole.objects.filter(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
        ).values_list("role_id", flat=True)
    )


def role_code_exists(tenant_id: int, code: str, *, exclude_role_id: Optional[int] = None) -> bool:
    queryset = Role.objects.filter(tenant_id=tenant_id, code=code)
    if exclude_role_id is not None:
        queryset = queryset.exclude(role_id=exclude_role_id)
    return queryset.exists()


def role_name_exists(tenant_id: int, name: str, *, exclude_role_id: Optional[int] = None) -> bool:
    queryset = Role.objects.filter(tenant_id=tenant_id, name=name)
    if exclude_role_id is not None:
        queryset = queryset.exclude(role_id=exclude_role_id)
    return queryset.exists()
