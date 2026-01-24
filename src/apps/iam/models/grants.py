"""
RolePermission 模型：资源级授权记录
"""
from django.db import models

from apps.iam.models.roles import Role
from apps.resource_tree.models.resource_node import ResourceTreeNode
from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class ResourceType(models.TextChoices):
    """资源类型枚举"""

    TABLE_SCHEMA = "TABLE_SCHEMA", "表结构"
    TABLE_DATA = "TABLE_DATA", "表数据"
    FLOW = "FLOW", "流程"
    DATASET = "DATASET", "数据集"
    DASHBOARD = "DASHBOARD", "看板"


class PermissionLevel(models.TextChoices):
    """资源权限等级"""

    NONE = "NONE", "无权限"
    VIEW = "VIEW", "可查看"
    EDIT = "EDIT", "可编辑"
    MANAGE = "MANAGE", "可管理"


class RolePermission(models.Model):
    """
    资源级权限

    tech.md §5.10.3 `role_permission`：
    - tenant_id / role_id / resource_type / resource_tree_node_id / permission
    """

    role_permission_id = models.BigAutoField(primary_key=True, help_text="记录ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="role_permissions",
        db_column="tenant_id",
        help_text="租户",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="resource_permissions",
        db_column="role_id",
        help_text="角色",
    )
    resource_type = models.CharField(
        max_length=32,
        choices=ResourceType.choices,
        help_text="资源类型",
    )
    resource_tree_node = models.ForeignKey(
        ResourceTreeNode,
        on_delete=models.CASCADE,
        related_name="role_permissions",
        db_column="resource_tree_node_id",
        help_text="资源树节点",
    )
    permission = models.CharField(
        max_length=16,
        choices=PermissionLevel.choices,
        default=PermissionLevel.NONE,
        help_text="权限等级",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_role_permissions",
        db_column="created_by",
        help_text="创建人（tenant_user_id）",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="updated_role_permissions",
        db_column="updated_by",
        help_text="更新人（tenant_user_id）",
    )

    class Meta:
        db_table = "role_permission"
        unique_together = [["tenant", "role", "resource_type", "resource_tree_node"]]
        indexes = [
            models.Index(
                fields=["tenant", "role", "resource_type", "resource_tree_node"],
                name="uk_role_perm",
            ),
            models.Index(
                fields=["tenant", "resource_tree_node"],
                name="idx_perm_node",
            ),
            models.Index(fields=["tenant", "role"], name="idx_perm_role"),
        ]

    def __str__(self) -> str:
        return (
            "RolePermission("
            f"role_permission_id={self.role_permission_id}, "
            f"tenant_id={self.tenant_id}, role_id={self.role_id}, "
            f"resource_type={self.resource_type}, permission={self.permission}"
            ")"
        )

