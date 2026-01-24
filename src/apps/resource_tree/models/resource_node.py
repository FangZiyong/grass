"""
ResourceTreeNode 模型：资源树节点
"""
from django.db import models

from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


class ResourceScope(models.TextChoices):
    """资源域（scope）"""

    TABLE = "TABLE", "表"
    FLOW = "FLOW", "流程"
    DATASET = "DATASET", "数据集"
    DASHBOARD = "DASHBOARD", "仪表盘"


class ResourceNodeType(models.TextChoices):
    """资源树节点类型"""

    FOLDER = "FOLDER", "文件夹"
    RESOURCE = "RESOURCE", "资源"


class ResourceTreeNode(models.Model):
    """
    资源树节点

    对照 OpenAPI ResourceTreeNodeDTO：
    - node_id/tenant_id/scope/node_type/name/parent_node_id
    - ref_type/ref_resource_id/sort_order/path/depth
    - created_by/updated_by/is_deleted
    """

    node_id = models.BigAutoField(primary_key=True, help_text="节点ID")
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="resource_tree_nodes",
        db_column="tenant_id",
        help_text="租户",
    )
    scope = models.CharField(
        max_length=16,
        choices=ResourceScope.choices,
        db_index=True,
        help_text="资源域（scope）",
    )
    node_type = models.CharField(
        max_length=16,
        choices=ResourceNodeType.choices,
        default=ResourceNodeType.FOLDER,
        help_text="节点类型：FOLDER/RESOURCE",
    )
    name = models.CharField(
        max_length=128,
        help_text="节点名称",
    )
    parent_node = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        db_column="parent_node_id",
        help_text="父节点",
    )
    ref_type = models.CharField(
        max_length=32,
        choices=ResourceScope.choices,
        null=True,
        blank=True,
        help_text="资源类型（仅 node_type=RESOURCE 时存在）",
    )
    ref_resource_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="资源引用ID（仅 node_type=RESOURCE 时存在）",
    )
    sort_order = models.IntegerField(
        default=0,
        help_text="同级排序",
    )
    path = models.CharField(
        max_length=1024,
        blank=True,
        default="/",
        help_text="节点路径缓存（必须以 / 开头结尾）",
    )
    depth = models.IntegerField(
        default=0,
        help_text="层级深度",
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="软删除标记",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="created_resource_tree_nodes",
        db_column="created_by",
        help_text="创建人（tenant_user_id）",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.PROTECT,
        related_name="updated_resource_tree_nodes",
        db_column="updated_by",
        help_text="更新人（tenant_user_id）",
    )

    ROOT_NAME = "ROOT"
    ROOT_DEPTH = 0

    class Meta:
        db_table = "resource_tree_node"
        unique_together = [["tenant", "scope", "parent_node", "node_type", "name"]]
        indexes = [
            models.Index(
                fields=["tenant", "scope", "parent_node", "sort_order"],
                name="idx_tree_parent",
            ),
            models.Index(
                fields=["tenant", "scope", "ref_type", "ref_resource_id"],
                name="idx_tree_ref",
            ),
        ]

    def __str__(self) -> str:
        return (
            "ResourceTreeNode("
            f"node_id={self.node_id}, tenant_id={self.tenant_id}, "
            f"scope={self.scope}, node_type={self.node_type}"
            ")"
        )

    @classmethod
    def ensure_root_nodes_for_tenant(cls, tenant: Tenant) -> list["ResourceTreeNode"]:
        """
        为指定租户补齐各 scope 的 ROOT 节点（幂等）。
        """
        actor = (
            TenantUser.objects.filter(tenant=tenant, is_owner=True).first()
            or TenantUser.objects.filter(tenant=tenant).first()
        )
        if actor is None:
            raise ValueError(f"tenant={tenant.tenant_id} lacks tenant_user for root init")
        roots: list["ResourceTreeNode"] = []
        for scope in ResourceScope.values:
            node, _ = cls.objects.get_or_create(
                tenant=tenant,
                scope=scope,
                parent_node=None,
                node_type=ResourceNodeType.FOLDER,
                ref_type=None,
                ref_resource_id=None,
                defaults={
                    "name": cls.ROOT_NAME,
                    "sort_order": 0,
                    "depth": cls.ROOT_DEPTH,
                    "path": "/",
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            if not node.path:
                node.path = f"/{node.node_id}/"
                node.depth = cls.ROOT_DEPTH
                node.sort_order = 0
                node.name = cls.ROOT_NAME
                node.created_by = actor
                node.updated_by = actor
                node.save(
                    update_fields=[
                        "path",
                        "depth",
                        "sort_order",
                        "name",
                        "created_by",
                        "updated_by",
                    ]
                )
            roots.append(node)
        return roots

