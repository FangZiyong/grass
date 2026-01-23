"""
RowPermission 模型：行级权限规则
"""
from django.db import models

from apps.iam.models.roles import Role
from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class RowPermissionStatus(models.TextChoices):
    """行权限状态枚举"""

    ACTIVE = "ACTIVE", "活跃"
    DISABLED = "DISABLED", "已禁用"


class RowPermission(models.Model):
    """
    行权限规则

    tech.md §5.10.4 `row_permission`：
    - tenant_id / role_id / table_id / filter_dsl / status
    """

    row_permission_id = models.BigAutoField(primary_key=True, help_text="规则ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="row_permissions",
        db_column="tenant_id",
        help_text="租户",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="row_permissions",
        db_column="role_id",
        help_text="角色",
    )
    table_id = models.BigIntegerField(
        help_text="表ID（FK → modeling_table.table_id）",
    )
    name = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="规则名称",
    )
    filter_dsl = models.JSONField(
        help_text="行过滤 DSL（FilterDSL）",
    )
    status = models.CharField(
        max_length=16,
        choices=RowPermissionStatus.choices,
        default=RowPermissionStatus.ACTIVE,
        help_text="规则状态",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_row_permissions",
        db_column="created_by",
        help_text="创建人（tenant_user_id）",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="updated_row_permissions",
        db_column="updated_by",
        help_text="更新人（tenant_user_id）",
    )

    class Meta:
        db_table = "row_permission"
        unique_together = [["tenant", "role", "table_id"]]
        indexes = [
            models.Index(fields=["tenant", "role", "table_id"], name="uk_rowperm"),
            models.Index(fields=["tenant", "table_id"], name="idx_rowperm_table"),
        ]

    def __str__(self) -> str:
        return (
            "RowPermission("
            f"row_permission_id={self.row_permission_id}, tenant_id={self.tenant_id}, "
            f"role_id={self.role_id}, table_id={self.table_id}, status={self.status}"
            ")"
        )

