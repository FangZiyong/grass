"""
resource_tree 查询层（Selectors）

提供只读查询操作，不包含业务写逻辑。
"""
from typing import Optional

from django.db.models import QuerySet

from apps.resource_tree.models import ResourceNodeType, ResourceScope, ResourceTreeNode


def get_root_node(tenant_id: int, scope: str) -> Optional[ResourceTreeNode]:
    """
    获取指定租户和scope的根节点。
    
    Args:
        tenant_id: 租户ID
        scope: 资源域（TABLE/FLOW/DATASET/DASHBOARD）
    
    Returns:
        根节点，不存在返回 None
    """
    return ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node=None,
        is_deleted=False,
    ).first()


def get_node_by_id(tenant_id: int, scope: str, node_id: int) -> Optional[ResourceTreeNode]:
    """
    根据ID获取节点（校验租户和scope归属）。
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        node_id: 节点ID
    
    Returns:
        节点，不存在或不属于该租户/scope返回 None
    """
    return ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        node_id=node_id,
        is_deleted=False,
    ).first()


def list_children(
    tenant_id: int,
    scope: str,
    parent_node_id: Optional[int] = None,
    include_resources: bool = True,
) -> QuerySet[ResourceTreeNode]:
    """
    查询指定节点的子节点列表。
    
    Args:
        tenant_id: 租户ID
        scope: 资源域（TABLE/FLOW/DATASET/DASHBOARD）
        parent_node_id: 父节点ID，None表示查询根节点的子节点
        include_resources: 是否包含资源节点，False则只返回文件夹
    
    Returns:
        按 sort_order 排序的子节点列表
    """
    # 构建基础查询
    queryset = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        is_deleted=False,
    )
    
    # 处理父节点条件
    if parent_node_id is None:
        # 查询根节点的直接子节点
        # 首先获取根节点
        root = get_root_node(tenant_id, scope)
        if root is None:
            return ResourceTreeNode.objects.none()
        queryset = queryset.filter(parent_node_id=root.node_id)
    else:
        queryset = queryset.filter(parent_node_id=parent_node_id)
    
    # 是否只返回文件夹
    if not include_resources:
        queryset = queryset.filter(node_type=ResourceNodeType.FOLDER)
    
    # 按 sort_order 排序
    return queryset.order_by("sort_order", "node_id")


def is_valid_scope(scope: str) -> bool:
    """
    检查 scope 是否有效。
    
    Args:
        scope: 资源域
    
    Returns:
        是否为有效的 scope 值
    """
    return scope in ResourceScope.values
