"""
TenantUserRole 模型：成员-角色关系
"""
from django.db import models

from apps.iam.models.roles import Role
from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class TenantUserRole(models.Model):
    """
    成员-角色关联

    tech.md §5.10.2 `tenant_user_role`：
    - tenant_id / tenant_user_id / role_id
    - created_by
    """

    tenant_user_role_id = models.BigAutoField(primary_key=True, help_text="记录ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="tenant_user_roles",
        db_column="tenant_id",
        help_text="租户",
    )
    tenant_user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name="role_bindings",
        db_column="tenant_user_id",
        help_text="租户成员",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_bindings",
        db_column="role_id",
        help_text="角色",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_role_bindings",
        db_column="created_by",
        help_text="操作人（tenant_user_id）",
    )

    class Meta:
        db_table = "tenant_user_role"
        unique_together = [["tenant", "tenant_user", "role"]]
        indexes = [
            models.Index(
                fields=["tenant", "tenant_user", "role"],
                name="uk_user_role",
            ),
            models.Index(fields=["tenant", "role"], name="idx_role_users"),
        ]

    def __str__(self) -> str:
        return (
            "TenantUserRole("
            f"tenant_user_role_id={self.tenant_user_role_id}, "
            f"tenant_id={self.tenant_id}, tenant_user_id={self.tenant_user_id}, "
            f"role_id={self.role_id}"
            ")"
        )

