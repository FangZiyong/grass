"""
resource_tree 服务层（写操作）

实现资源树节点的业务写操作。
"""
from django.db import models, transaction
from django.db.utils import IntegrityError

from apps.resource_tree.models import ResourceNodeType, ResourceTreeNode
from apps.resource_tree.selectors import get_all_descendants, get_node_by_id, get_root_node
from apps.tenants.models.tenant_user import TenantUser
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


def create_folder(
    *,
    tenant_id: int,
    scope: str,
    parent_node_id: int | None,
    name: str,
    actor: TenantUser,
) -> ResourceTreeNode:
    """
    创建文件夹节点
    
    对照 tech.md §6.2.5.2:
    - 校验 parent 属于同 tenant+scope
    - 创建节点并分配 order
    - 审计：FOLDER_CREATE（TODO：等审计模块实现后补充）
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        parent_node_id: 父节点ID，None表示在根节点下创建
        name: 文件夹名称（1~64字符）
        actor: 操作人（TenantUser）
    
    Returns:
        创建的文件夹节点
    
    Raises:
        GrassAPIException: 各种业务异常
    """
    # 1. 校验名称长度
    if not name or len(name) < 1 or len(name) > 64:
        raise GrassAPIException(
            detail="文件夹名称长度必须在1~64字符之间",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )
    
    # 2. 获取父节点并校验归属
    if parent_node_id is None:
        # 在根节点下创建
        parent_node = get_root_node(tenant_id, scope)
        if parent_node is None:
            raise GrassAPIException(
                detail="根节点不存在，无法创建文件夹",
                status_code=404,
                code="RESOURCE_NODE_NOT_FOUND",
            )
    else:
        parent_node = get_node_by_id(tenant_id, scope, parent_node_id)
        if parent_node is None:
            raise GrassAPIException(
                detail=f"父节点不存在: {parent_node_id}",
                status_code=404,
                code="RESOURCE_NODE_NOT_FOUND",
            )
        
        # 父节点必须是文件夹
        if parent_node.node_type != ResourceNodeType.FOLDER:
            raise GrassAPIException(
                detail="父节点必须是文件夹",
                status_code=400,
                code=ErrorCode.BAD_REQUEST,
            )
    
    # 3. 检查同级唯一约束（tenant + scope + parent_node + node_type + name）
    sibling_query = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node=parent_node,
        node_type=ResourceNodeType.FOLDER,
        name=name,
        is_deleted=False,
    )
    
    if sibling_query.exists():
        raise GrassAPIException(
            detail=f"同级节点已存在同名文件夹: {name}",
            status_code=409,
            code="NAME_CONFLICT",
        )
    
    # 4. 计算新的sort_order（追加到末尾）
    siblings = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node=parent_node,
        is_deleted=False,
    ).order_by("sort_order", "node_id")
    
    if siblings.exists():
        max_order = siblings.aggregate(models.Max("sort_order"))["sort_order__max"]
        new_sort_order = (max_order or 0) + 1
    else:
        new_sort_order = 0
    
    # 5. 计算新的path和depth
    new_path = f"{parent_node.path}{parent_node.node_id}/"
    new_depth = parent_node.depth + 1
    
    # 6. 创建文件夹节点
    try:
        with transaction.atomic():
            folder = ResourceTreeNode.objects.create(
                tenant_id=tenant_id,
                scope=scope,
                node_type=ResourceNodeType.FOLDER,
                name=name,
                parent_node=parent_node,
                sort_order=new_sort_order,
                path=new_path,
                depth=new_depth,
                created_by=actor,
                updated_by=actor,
            )
    except IntegrityError as e:
        # 捕获唯一约束冲突（虽然已检查，但并发情况下仍可能发生）
        raise GrassAPIException(
            detail=f"文件夹名称冲突: {name}",
            status_code=409,
            code="NAME_CONFLICT",
        ) from e
    
    return folder


def rename_node(
    *,
    tenant_id: int,
    scope: str,
    node_id: int,
    new_name: str,
    actor: TenantUser,
) -> ResourceTreeNode:
    """
    重命名资源树节点
    
    对照 tech.md §6.2.5.3:
    - 校验 node 归属（tenant_id + scope）
    - 更新 name 并处理同级唯一冲突
    - 不支持改 scope/type
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        node_id: 节点ID
        new_name: 新名称（1~64字符）
        actor: 操作人（TenantUser）
    
    Returns:
        更新后的节点
    
    Raises:
        GrassAPIException: 各种业务异常
    """
    # 1. 校验名称长度
    if not new_name or len(new_name) < 1 or len(new_name) > 64:
        raise GrassAPIException(
            detail="节点名称长度必须在1~64字符之间",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )
    
    # 2. 获取节点并校验归属
    node = get_node_by_id(tenant_id, scope, node_id)
    if node is None:
        raise GrassAPIException(
            detail=f"节点不存在: {node_id}",
            status_code=404,
            code="RESOURCE_NODE_NOT_FOUND",
        )
    
    # 3. 检查是否为根节点（根节点不允许重命名）
    if node.parent_node is None and node.name == ResourceTreeNode.ROOT_NAME:
        raise GrassAPIException(
            detail="根节点不允许重命名",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )
    
    # 4. 如果名称未变化，直接返回
    if node.name == new_name:
        return node
    
    # 5. 检查同级唯一约束（tenant + scope + parent_node + node_type + name）
    # 查询同级节点是否已有同名节点
    sibling_query = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node=node.parent_node,
        node_type=node.node_type,
        name=new_name,
        is_deleted=False,
    ).exclude(node_id=node_id)
    
    if sibling_query.exists():
        raise GrassAPIException(
            detail=f"同级节点已存在同名节点: {new_name}",
            status_code=409,
            code="NAME_CONFLICT",
        )
    
    # 6. 更新节点名称
    try:
        with transaction.atomic():
            node.name = new_name
            node.updated_by = actor
            node.save(update_fields=["name", "updated_by", "updated_at"])
    except IntegrityError as e:
        # 捕获唯一约束冲突（虽然已检查，但并发情况下仍可能发生）
        raise GrassAPIException(
            detail=f"节点名称冲突: {new_name}",
            status_code=409,
            code="NAME_CONFLICT",
        ) from e
    
    return node


def move_node(
    *,
    tenant_id: int,
    scope: str,
    node_id: int,
    target_parent_node_id: int | None,
    target_index: int | None = None,
    actor: TenantUser,
) -> ResourceTreeNode:
    """
    移动节点到新的父节点
    
    对照 tech.md §6.2.5.4:
    - 校验 src/dst
    - 防循环（不能移入自身子树）
    - 更新 parent_node_id/order
    - 更新 path/depth（递归更新所有子节点）
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        node_id: 要移动的节点ID
        target_parent_node_id: 目标父节点ID，None表示移动到根节点
        target_index: 目标位置索引（可选；不传则追加到末尾）
        actor: 操作人（TenantUser）
    
    Returns:
        移动后的节点
    
    Raises:
        GrassAPIException: 各种业务异常
    """
    # 1. 获取源节点并校验归属
    source_node = get_node_by_id(tenant_id, scope, node_id)
    if source_node is None:
        raise GrassAPIException(
            detail=f"节点不存在: {node_id}",
            status_code=404,
            code="RESOURCE_NODE_NOT_FOUND",
        )
    
    # 2. 检查是否为根节点（根节点不允许移动）
    if source_node.parent_node is None and source_node.name == ResourceTreeNode.ROOT_NAME:
        raise GrassAPIException(
            detail="根节点不允许移动",
            status_code=400,
            code=ErrorCode.BAD_REQUEST,
        )
    
    # 3. 获取目标父节点
    if target_parent_node_id is None:
        # 移动到根节点
        target_parent = get_root_node(tenant_id, scope)
        if target_parent is None:
            raise GrassAPIException(
                detail="根节点不存在",
                status_code=404,
                code="RESOURCE_NODE_NOT_FOUND",
            )
    else:
        target_parent = get_node_by_id(tenant_id, scope, target_parent_node_id)
        if target_parent is None:
            raise GrassAPIException(
                detail=f"目标父节点不存在: {target_parent_node_id}",
                status_code=404,
                code="RESOURCE_NODE_NOT_FOUND",
            )
        
        # 目标父节点必须是文件夹
        if target_parent.node_type != ResourceNodeType.FOLDER:
            raise GrassAPIException(
                detail="目标父节点必须是文件夹",
                status_code=400,
                code=ErrorCode.BAD_REQUEST,
            )
    
    # 4. 防止循环：不能移入自身子树
    if target_parent.node_id == source_node.node_id:
        raise GrassAPIException(
            detail="不能将节点移动到自身",
            status_code=400,
            code="INVALID_MOVE",
        )
    
    # 检查目标父节点是否是源节点的后代
    descendants = get_all_descendants(tenant_id, scope, source_node.node_id)
    if descendants.filter(node_id=target_parent.node_id).exists():
        raise GrassAPIException(
            detail="不能将节点移动到其子节点下",
            status_code=400,
            code="INVALID_MOVE",
        )
    
    # 5. 如果目标父节点就是当前父节点，只需要调整sort_order
    if source_node.parent_node_id == target_parent.node_id:
        # 只需要调整排序
        _reorder_node_in_parent(
            tenant_id=tenant_id,
            scope=scope,
            node_id=node_id,
            target_parent_node_id=target_parent.node_id,
            target_index=target_index,
            actor=actor,
        )
        # 重新加载节点
        source_node.refresh_from_db()
        return source_node
    
    # 6. 计算新的sort_order
    new_sort_order = _calculate_new_sort_order(
        tenant_id=tenant_id,
        scope=scope,
        target_parent_node_id=target_parent.node_id,
        target_index=target_index,
    )
    
    # 7. 计算新的path和depth
    new_path = f"{target_parent.path}{target_parent.node_id}/"
    new_depth = target_parent.depth + 1
    
    # 8. 在事务中执行移动操作
    try:
        with transaction.atomic():
            # 更新源节点
            old_parent_id = source_node.parent_node_id
            source_node.parent_node_id = target_parent.node_id
            source_node.sort_order = new_sort_order
            source_node.path = new_path
            source_node.depth = new_depth
            source_node.updated_by = actor
            source_node.save(
                update_fields=[
                    "parent_node_id",
                    "sort_order",
                    "path",
                    "depth",
                    "updated_by",
                    "updated_at",
                ]
            )
            
            # 递归更新所有子节点的path和depth
            _update_descendants_path_and_depth(
                tenant_id=tenant_id,
                scope=scope,
                parent_node_id=source_node.node_id,
                base_path=new_path,
                base_depth=new_depth,
            )
            
            # 调整原父节点下其他节点的sort_order（如果原父节点存在）
            if old_parent_id is not None:
                _reorder_siblings_after_move(
                    tenant_id=tenant_id,
                    scope=scope,
                    parent_node_id=old_parent_id,
                    moved_node_id=node_id,
                )
            
            # 调整新父节点下其他节点的sort_order
            _reorder_siblings_after_move(
                tenant_id=tenant_id,
                scope=scope,
                parent_node_id=target_parent.node_id,
                moved_node_id=node_id,
                new_sort_order=new_sort_order,
            )
            
    except IntegrityError as e:
        raise GrassAPIException(
            detail="移动节点失败：可能与其他节点冲突",
            status_code=409,
            code="NAME_CONFLICT",
        ) from e
    
    # 重新加载节点
    source_node.refresh_from_db()
    return source_node


def _calculate_new_sort_order(
    tenant_id: int,
    scope: str,
    target_parent_node_id: int | None,
    target_index: int | None,
) -> int:
    """
    计算节点在新父节点下的sort_order
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        target_parent_node_id: 目标父节点ID
        target_index: 目标位置索引（可选）
    
    Returns:
        新的sort_order值
    """
    # 查询目标父节点下的所有子节点
    children = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node_id=target_parent_node_id,
        is_deleted=False,
    ).order_by("sort_order", "node_id")
    
    if target_index is None:
        # 追加到末尾
        if children.exists():
            max_order = children.aggregate(models.Max("sort_order"))["sort_order__max"]
            return (max_order or 0) + 1
        else:
            return 0
    else:
        # 插入到指定位置
        children_list = list(children)
        if target_index >= len(children_list):
            # 超出范围，追加到末尾
            if children_list:
                max_order = max(node.sort_order for node in children_list)
                return max_order + 1
            else:
                return 0
        else:
            # 插入到指定位置，需要重新分配sort_order
            # 为了简化，我们使用target_index * 10作为初始值
            # 如果与现有值冲突，则重新分配所有节点的sort_order
            base_order = target_index * 10
            conflicting = children.filter(sort_order=base_order).exists()
            if conflicting:
                # 重新分配所有节点的sort_order
                for idx, child in enumerate(children_list):
                    if idx >= target_index:
                        child.sort_order = (idx + 1) * 10
                    else:
                        child.sort_order = idx * 10
                    child.save(update_fields=["sort_order"])
                return target_index * 10
            else:
                return base_order


def _reorder_node_in_parent(
    tenant_id: int,
    scope: str,
    node_id: int,
    target_parent_node_id: int,
    target_index: int | None,
    actor: TenantUser,
) -> None:
    """
    在同一父节点下调整节点的sort_order
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        node_id: 节点ID
        target_parent_node_id: 父节点ID
        target_index: 目标位置索引
        actor: 操作人
    """
    # 获取所有同级节点（排除当前节点）
    siblings = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node_id=target_parent_node_id,
        is_deleted=False,
    ).exclude(node_id=node_id).order_by("sort_order", "node_id")
    
    siblings_list = list(siblings)
    
    if target_index is None:
        # 移动到末尾
        max_order = siblings.aggregate(models.Max("sort_order"))["sort_order__max"] if siblings.exists() else -1
        new_order = max_order + 1 if max_order is not None else 0
    else:
        # 插入到指定位置
        if target_index >= len(siblings_list):
            # 超出范围，移动到末尾
            max_order = max((node.sort_order for node in siblings_list), default=-1)
            new_order = max_order + 1
        else:
            # 插入到指定位置，需要重新分配sort_order
            new_order = target_index * 10
            # 检查是否有冲突
            if siblings.filter(sort_order=new_order).exists():
                # 重新分配所有节点的sort_order
                all_nodes = list(siblings) + [ResourceTreeNode.objects.get(node_id=node_id)]
                all_nodes.sort(key=lambda n: (n.sort_order, n.node_id))
                # 找到当前节点应该插入的位置
                current_node = ResourceTreeNode.objects.get(node_id=node_id)
                insert_pos = target_index
                for idx, node in enumerate(all_nodes):
                    if node.node_id == node_id:
                        continue
                    if idx < insert_pos:
                        node.sort_order = idx * 10
                    else:
                        node.sort_order = (idx + 1) * 10
                    node.save(update_fields=["sort_order"])
                current_node.sort_order = insert_pos * 10
                current_node.updated_by = actor
                current_node.save(update_fields=["sort_order", "updated_by", "updated_at"])
                return
    
    # 更新节点sort_order
    node = ResourceTreeNode.objects.get(node_id=node_id)
    node.sort_order = new_order
    node.updated_by = actor
    node.save(update_fields=["sort_order", "updated_by", "updated_at"])


def _update_descendants_path_and_depth(
    tenant_id: int,
    scope: str,
    parent_node_id: int,
    base_path: str,
    base_depth: int,
) -> None:
    """
    递归更新所有子节点的path和depth
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        parent_node_id: 父节点ID
        base_path: 基础路径（父节点的path）
        base_depth: 基础深度（父节点的depth）
    """
    # 获取直接子节点
    children = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node_id=parent_node_id,
        is_deleted=False,
    )
    
    for child in children:
        # 更新当前子节点的path和depth
        child.path = f"{base_path}{child.node_id}/"
        child.depth = base_depth + 1
        child.save(update_fields=["path", "depth"])
        
        # 递归更新子节点的子节点
        _update_descendants_path_and_depth(
            tenant_id=tenant_id,
            scope=scope,
            parent_node_id=child.node_id,
            base_path=child.path,
            base_depth=child.depth,
        )


def _reorder_siblings_after_move(
    tenant_id: int,
    scope: str,
    parent_node_id: int,
    moved_node_id: int,
    new_sort_order: int | None = None,
) -> None:
    """
    移动节点后，调整同级节点的sort_order，确保连续
    
    Args:
        tenant_id: 租户ID
        scope: 资源域
        parent_node_id: 父节点ID
        moved_node_id: 被移动的节点ID（排除在外）
        new_sort_order: 新节点的sort_order（如果提供，用于插入位置）
    """
    # 获取所有同级节点（排除被移动的节点）
    siblings = ResourceTreeNode.objects.filter(
        tenant_id=tenant_id,
        scope=scope,
        parent_node_id=parent_node_id,
        is_deleted=False,
    ).exclude(node_id=moved_node_id).order_by("sort_order", "node_id")
    
    # 如果新节点有指定的sort_order，需要确保不冲突
    if new_sort_order is not None:
        # 检查是否有冲突
        conflicting = siblings.filter(sort_order=new_sort_order).exists()
        if conflicting:
            # 重新分配所有节点的sort_order，确保连续
            all_siblings = list(siblings)
            for idx, sibling in enumerate(all_siblings):
                if sibling.sort_order >= new_sort_order:
                    sibling.sort_order = new_sort_order + idx + 1
                else:
                    sibling.sort_order = idx
                sibling.save(update_fields=["sort_order"])
