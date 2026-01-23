"""
IAM 服务层（写操作）
"""
from typing import Optional

from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.iam.selectors import get_role_by_id, role_code_exists, role_name_exists
from apps.tenants.models.tenant_user import TenantUser
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


def _ensure_manage_permission(actor: Optional[TenantUser]) -> None:
    """
    校验角色管理权限。

    当前仅支持 Owner 判定（权限引擎未实现）。
    """
    if actor is None:
        raise GrassAPIException(
            detail="缺少租户上下文",
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
        )
    if not actor.is_owner:
        raise GrassAPIException(
            detail="无权限执行该操作",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )


def create_role(
    *,
    tenant_id: int,
    actor: TenantUser,
    code: str,
    name: str,
    description: Optional[str] = None,
) -> Role:
    """
    创建角色。
    """
    _ensure_manage_permission(actor)
    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
            status_code=403,
            code=ErrorCode.PERMISSION_DENIED,
        )

    if role_code_exists(tenant_id, code):
        raise GrassAPIException(
            detail="角色编码已存在",
            status_code=409,
            code="ROLE_CODE_DUPLICATE",
        )
    if role_name_exists(tenant_id, name):
        raise GrassAPIException(
            detail="角色名称已存在",
            status_code=409,
            code="ROLE_NAME_CONFLICT",
        )

    return Role.objects.create(
        tenant_id=tenant_id,
        code=code,
        name=name,
        description=description,
        status=RoleStatus.ACTIVE,
        created_by=actor,
        updated_by=actor,
    )


def update_role(
    *,
    tenant_id: int,
    role_id: int,
    actor: TenantUser,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
) -> Role:
    """
    更新角色。
    """
    _ensure_manage_permission(actor)
    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    if name is not None and role_name_exists(tenant_id, name, exclude_role_id=role.role_id):
        raise GrassAPIException(
            detail="角色名称已存在",
            status_code=409,
            code="ROLE_NAME_CONFLICT",
        )

    updated_fields = []
    if name is not None:
        role.name = name
        updated_fields.append("name")
    if description is not None:
        role.description = description
        updated_fields.append("description")
    if status is not None:
        role.status = status
        updated_fields.append("status")

    if updated_fields:
        role.updated_by = actor
        updated_fields.append("updated_by")
        role.save(update_fields=updated_fields + ["updated_at"])

    return role


def delete_role(*, tenant_id: int, role_id: int, actor: TenantUser) -> None:
    """
    删除角色。
    """
    _ensure_manage_permission(actor)
    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    if role.is_builtin:
        raise GrassAPIException(
            detail="内置角色不可删除",
            status_code=409,
            code="ROLE_BUILTIN_CANNOT_DELETE",
        )

    if TenantUserRole.objects.filter(tenant_id=tenant_id, role_id=role_id).exists():
        raise GrassAPIException(
            detail="角色仍被成员绑定",
            status_code=409,
            code="ROLE_IN_USE",
        )

    role.delete()
