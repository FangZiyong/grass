"""
Tenant 服务层（写操作）
"""
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus
from apps.tenants.selectors import get_tenant_by_id, get_tenant_user
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


def switch_tenant(user_id: int, tenant_id: int) -> dict:
    """
    切换租户上下文
    
    根据 tech.md §4.7.3：
    - 校验tenant存在
    - 校验tenant状态为ACTIVE
    - 校验TenantUser存在且为ACTIVE
    - 更新global_user.last_tenant_id（这里先返回，后续T1.5会实现）
    
    Args:
        user_id: 用户ID
        tenant_id: 目标租户ID
        
    Returns:
        {tenant_id, redirect_url}
        
    Raises:
        GrassAPIException: 各种业务异常
    """
    tenant = get_tenant_by_id(tenant_id)
    if tenant is None:
        raise GrassAPIException(
            detail="租户不存在",
            status_code=404,
            code=ErrorCode.NOT_FOUND,
        )
    
    if tenant.status != TenantStatus.ACTIVE:
        raise GrassAPIException(
            detail="租户已停用",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )
    
    tenant_user = get_tenant_user(tenant_id, user_id)
    if tenant_user is None:
        raise GrassAPIException(
            detail="用户不属于该租户",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )
    
    if tenant_user.status != TenantUserStatus.ACTIVE:
        raise GrassAPIException(
            detail="用户在该租户中已被禁用",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )
    
    # 更新last_login（可选，按需求）
    with transaction.atomic():
        tenant_user.last_login = timezone.now()
        tenant_user.save(update_fields=["last_login", "updated_at"])
    
    # TODO: 更新global_user.last_tenant_id（T1.5任务）
    
    return {
        "tenant_id": tenant_id,
        "redirect_url": f"/t/{tenant_id}",
    }

