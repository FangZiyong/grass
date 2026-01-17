"""
Tenant 查询层（只读操作）
"""
from typing import Optional

from django.db.models import QuerySet

from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


def get_tenant_by_id(tenant_id: int) -> Optional[Tenant]:
    """
    根据ID获取租户
    
    Args:
        tenant_id: 租户ID
        
    Returns:
        Tenant对象或None
    """
    try:
        return Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return None


def get_tenant_user(tenant_id: int, user_id: int) -> Optional[TenantUser]:
    """
    获取租户成员关系
    
    Args:
        tenant_id: 租户ID
        user_id: 用户ID
        
    Returns:
        TenantUser对象或None
    """
    try:
        return TenantUser.objects.get(tenant_id=tenant_id, user_id=user_id)
    except TenantUser.DoesNotExist:
        return None


def list_user_tenants(user_id: int, status: Optional[str] = None) -> QuerySet[Tenant]:
    """
    获取用户所属的租户列表
    
    Args:
        user_id: 用户ID
        status: 可选的状态过滤（ACTIVE/SUSPENDED），默认返回所有
        
    Returns:
        租户QuerySet
    """
    tenant_ids = TenantUser.objects.filter(
        user_id=user_id,
        status=TenantUserStatus.ACTIVE,
    ).values_list("tenant_id", flat=True)
    
    queryset = Tenant.objects.filter(id__in=tenant_ids)
    
    if status:
        queryset = queryset.filter(status=status)
    
    return queryset.order_by("-created_at")

