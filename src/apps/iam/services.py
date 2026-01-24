"""
IAM 服务层（写操作）
"""
import re
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr

from apps.iam.models.grants import RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.iam.selectors import get_role_by_id, role_name_exists
from apps.tenants.models.tenant_user import TenantUser
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


_ROLE_AUTO_PREFIX = "ROLE_"
_ROLE_AUTO_START = 1000
_ROLE_AUTO_RE = re.compile(r"^ROLE_(\d+)$")


def _next_auto_role_code(*, tenant_id: int) -> str:
    """
    生成下一个租户内自增角色编码：ROLE_1000 起。

    说明：
    - 并发下依赖唯一约束 (tenant_id, code) + 重试保证不冲突。
    """
    base = _ROLE_AUTO_START - 1

    # 用 DB 聚合取最大序号，避免把所有 code 拉回 Python（数据量大时更稳）
    agg = (
        Role.objects.filter(
            tenant_id=tenant_id,
            code__startswith=_ROLE_AUTO_PREFIX,
        )
        .annotate(n=Cast(Substr("code", len(_ROLE_AUTO_PREFIX) + 1), IntegerField()))
        .aggregate(max_n=Max("n"))
    )
    max_n = agg.get("max_n")
    max_n = int(max_n) if max_n is not None else base
    return f"{_ROLE_AUTO_PREFIX}{max_n + 1}"


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

    if role_name_exists(tenant_id, name):
        raise GrassAPIException(
            detail="角色名称已存在",
            status_code=409,
            code="ROLE_NAME_CONFLICT",
        )

    # 后端自动生成 role_code：租户内递增 ROLE_1000 起
    last_err: Exception | None = None
    for _ in range(6):
        code = _next_auto_role_code(tenant_id=tenant_id)
        try:
            with transaction.atomic():
                return Role.objects.create(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    description=description,
                    status=RoleStatus.ACTIVE,
                    created_by=actor,
                    updated_by=actor,
                )
        except IntegrityError as e:
            # 可能由 (tenant_id, code) 唯一约束冲突触发，重试取下一个 code
            last_err = e
            continue
    raise GrassAPIException(
        detail="生成角色编码失败，请重试",
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
    ) from last_err


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


def _ensure_member_role_manage_permission(actor: Optional[TenantUser]) -> None:
    """
    校验成员角色绑定管理权限。

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


def _ensure_role_grant_manage_permission(actor: Optional[TenantUser]) -> None:
    """
    校验角色授权管理权限。

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


def bind_roles_to_user(
    *,
    tenant_id: int,
    tenant_user_id: int,
    role_ids: list[int],
    actor: TenantUser,
) -> list[int]:
    """
    给租户成员绑定角色（幂等追加）。
    """
    _ensure_member_role_manage_permission(actor)

    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    unique_role_ids = list(dict.fromkeys(role_ids))
    existing_roles = Role.objects.filter(
        tenant_id=tenant_id,
        role_id__in=unique_role_ids,
    ).values_list("role_id", flat=True)
    existing_role_ids = set(existing_roles)
    if len(existing_role_ids) != len(unique_role_ids):
        raise GrassAPIException(
            detail="角色不存在",
            status_code=404,
            code="ROLE_NOT_FOUND",
        )

    bound_role_ids = set(
        TenantUserRole.objects.filter(
            tenant_id=tenant_id,
            tenant_user_id=tenant_user_id,
            role_id__in=unique_role_ids,
        ).values_list("role_id", flat=True)
    )
    pending_role_ids = [rid for rid in unique_role_ids if rid not in bound_role_ids]
    if pending_role_ids:
        TenantUserRole.objects.bulk_create(
            [
                TenantUserRole(
                    tenant_id=tenant_id,
                    tenant_user_id=tenant_user_id,
                    role_id=role_id,
                    created_by=actor,
                )
                for role_id in pending_role_ids
            ],
            ignore_conflicts=True,
        )

    return unique_role_ids


def unbind_role_from_user(
    *,
    tenant_id: int,
    tenant_user_id: int,
    role_id: int,
    actor: TenantUser,
) -> bool:
    """
    解绑租户成员的角色（幂等）。
    """
    _ensure_member_role_manage_permission(actor)

    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    role = get_role_by_id(tenant_id, role_id)
    if role is None:
        raise GrassAPIException(
            detail="角色不存在",
            status_code=404,
            code="ROLE_NOT_FOUND",
        )

    deleted_count, _ = TenantUserRole.objects.filter(
        tenant_id=tenant_id,
        tenant_user_id=tenant_user_id,
        role_id=role_id,
    ).delete()
    return deleted_count > 0


def set_tenant_user_owner(
    *,
    tenant_id: int,
    tenant_user_id: int,
    actor: TenantUser,
) -> bool:
    """
    设为租户 Owner（幂等）。
    """
    _ensure_member_role_manage_permission(actor)

    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    if not tenant_user.is_owner:
        tenant_user.is_owner = True
        tenant_user.save(update_fields=["is_owner", "updated_at"])

    return tenant_user.is_owner


def unset_tenant_user_owner(
    *,
    tenant_id: int,
    tenant_user_id: int,
    actor: TenantUser,
) -> bool:
    """
    取消租户 Owner（幂等，保证至少 1 名 Owner）。
    """
    _ensure_member_role_manage_permission(actor)

    if actor.tenant_id != tenant_id:
        raise GrassAPIException(
            detail="跨租户操作被拒绝",
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

    if not tenant_user.is_owner:
        return False

    owner_count = TenantUser.objects.filter(tenant_id=tenant_id, is_owner=True).count()
    if owner_count <= 1:
        raise GrassAPIException(
            detail="至少保留 1 名 Owner",
            status_code=409,
            code="OWNER_MIN_ONE_VIOLATION",
        )

    tenant_user.is_owner = False
    tenant_user.save(update_fields=["is_owner", "updated_at"])
    return tenant_user.is_owner


def save_role_resource_permissions(
    *,
    tenant_id: int,
    role_id: int,
    items: list[dict],
    actor: TenantUser,
) -> int:
    """
    保存角色资源授权（按 resource_type 全量覆盖）。
    """
    _ensure_role_grant_manage_permission(actor)

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

    if not items:
        return 0

    resource_types = {item["resource_type"] for item in items}
    with transaction.atomic():
        RolePermission.objects.filter(
            tenant_id=tenant_id,
            role_id=role_id,
            resource_type__in=resource_types,
        ).delete()

        RolePermission.objects.bulk_create(
            [
                RolePermission(
                    tenant_id=tenant_id,
                    role_id=role_id,
                    resource_type=item["resource_type"],
                    resource_tree_node_id=item["resource_tree_node_id"],
                    permission=item["permission_level"],
                    created_by=actor,
                    updated_by=actor,
                )
                for item in items
            ]
        )

    return len(items)
