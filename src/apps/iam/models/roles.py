"""
Role 模型：租户内角色
"""
from django.db import models

from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class RoleStatus(models.TextChoices):
    """角色状态枚举"""

    ACTIVE = "ACTIVE", "活跃"
    DISABLED = "DISABLED", "已禁用"


class Role(models.Model):
    """
    角色模型

    tech.md §5.10.1 `role`：
    - tenant_id: 租户ID
    - code: 角色编码（租户内唯一）
    - name: 角色名称
    - description: 角色说明
    - is_builtin: 是否系统内置
    - status: ACTIVE/DISABLED
    - created_by / updated_by: 租户成员
    """

    role_id = models.BigAutoField(primary_key=True, help_text="角色ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="roles",
        db_column="tenant_id",
        help_text="租户",
    )
    code = models.CharField(
        max_length=64,
        help_text="角色编码（租户内唯一）",
    )
    name = models.CharField(
        max_length=64,
        help_text="角色名称",
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="角色说明",
    )
    is_builtin = models.BooleanField(
        default=False,
        help_text="是否系统内置",
    )
    status = models.CharField(
        max_length=16,
        choices=RoleStatus.choices,
        default=RoleStatus.ACTIVE,
        help_text="角色状态：ACTIVE=活跃，DISABLED=已禁用",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_roles",
        db_column="created_by",
        help_text="创建人（tenant_user_id）",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="updated_roles",
        db_column="updated_by",
        help_text="更新人（tenant_user_id）",
    )

    class Meta:
        db_table = "role"
        unique_together = [["tenant", "code"]]
        indexes = [
            models.Index(fields=["tenant", "code"], name="uk_role_code"),
            models.Index(fields=["tenant", "status"], name="idx_role_status"),
        ]

    def __str__(self) -> str:
        return (
            "Role("
            f"role_id={self.role_id}, tenant_id={self.tenant_id}, "
            f"code={self.code}, status={self.status}"
            ")"
        )

