"""
IAM 查询层（只读操作）
"""
from typing import Optional

from django.db.models import Q, QuerySet

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
