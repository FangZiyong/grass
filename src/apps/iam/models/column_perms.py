"""
ColumnPermission 模型：列级权限规则
"""
from django.db import models

from apps.iam.models.roles import Role
from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class ColumnAccessLevel(models.TextChoices):
    """列权限等级枚举"""

    HIDDEN = "HIDDEN", "不可见"
    READONLY = "READONLY", "只读"
    READWRITE = "READWRITE", "可写"


class ColumnPermission(models.Model):
    """
    列权限规则

    tech.md §5.10.5 `column_permission`：
    - tenant_id / role_id / table_id / field_id / access_level
    """

    column_permission_id = models.BigAutoField(primary_key=True, help_text="记录ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="column_permissions",
        db_column="tenant_id",
        help_text="租户",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="column_permissions",
        db_column="role_id",
        help_text="角色",
    )
    table_id = models.BigIntegerField(
        help_text="表ID（FK → modeling_table.table_id）",
    )
    field_id = models.BigIntegerField(
        help_text="字段ID（FK → modeling_field.field_id）",
    )
    access_level = models.CharField(
        max_length=16,
        choices=ColumnAccessLevel.choices,
        default=ColumnAccessLevel.READWRITE,
        help_text="列权限",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_column_permissions",
        db_column="created_by",
        help_text="创建人（tenant_user_id）",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="updated_column_permissions",
        db_column="updated_by",
        help_text="更新人（tenant_user_id）",
    )

    class Meta:
        db_table = "column_permission"
        unique_together = [["tenant", "role", "table_id", "field_id"]]
        indexes = [
            models.Index(
                fields=["tenant", "role", "table_id", "field_id"],
                name="uk_colperm",
            ),
            models.Index(
                fields=["tenant", "role", "table_id"],
                name="idx_colperm_role_table",
            ),
        ]

    def __str__(self) -> str:
        return (
            "ColumnPermission("
            f"column_permission_id={self.column_permission_id}, "
            f"tenant_id={self.tenant_id}, role_id={self.role_id}, "
            f"table_id={self.table_id}, field_id={self.field_id}, "
            f"access_level={self.access_level}"
            ")"
        )

