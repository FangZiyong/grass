"""
resource_tree API 视图

实现资源树相关接口：
- GET /api/resource-trees/{scope}/children - 查询子节点
- PATCH /api/resource-trees/{scope}/nodes/{node_id} - 重命名节点
"""
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.resource_tree.api.serializers import (
    ChildrenQuerySerializer,
    ChildrenResponseEnvelopeSerializer,
    FolderCreateRequestSerializer,
    FolderCreateResponseEnvelopeSerializer,
    MoveNodeRequestSerializer,
    MoveNodeResponseEnvelopeSerializer,
    ReorderRequestSerializer,
    ReorderResponseEnvelopeSerializer,
    RenameNodeRequestSerializer,
    RenameNodeResponseEnvelopeSerializer,
    ResourceTreeNodeSerializer,
)
from apps.resource_tree.models import ResourceScope
from apps.resource_tree.selectors import (
    get_node_by_id,
    get_root_node,
    is_valid_scope,
    list_children,
)
from apps.resource_tree.services import create_folder, move_node, rename_node
from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException
from common.http.response import envelope_response


def _node_to_dto(node) -> dict:
    """
    将 ResourceTreeNode 模型转换为 DTO 字典。
    
    对照 tech.md ResourceTreeNodeDTO 字段映射。
    """
    return {
        "node_id": node.node_id,
        "scope": node.scope,
        "node_type": node.node_type,
        "parent_node_id": node.parent_node_id,
        "name": node.name,
        "order_index": node.sort_order,
        "resource_type": node.ref_type,
        "resource_id": node.ref_resource_id,
    }


class FolderCreateView(APIView):
    """
    创建文件夹
    
    POST /api/resource-trees/{scope}/folders
    
    对照 tech.md §6.2.5.2:
    - 在指定 parent_node_id 下创建 folder 节点
    - 校验 parent 属于同 tenant+scope
    - 创建节点并分配 order
    - 审计：FOLDER_CREATE（TODO：等审计模块实现后补充）
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
        ],
        request=FolderCreateRequestSerializer,
        responses={
            200: FolderCreateResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="FolderCreateError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（非法scope/名称长度等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="FolderCreateError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="FolderCreateError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="FolderCreateError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="父节点不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="FolderCreateError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="名称冲突（同级节点已存在同名文件夹）",
            ),
        },
        tags=["ResourceTrees"],
        summary="创建文件夹",
        description="在指定 parent_node_id 下创建 folder 节点，并返回新节点。"
                    "如果不传 parent_node_id，则在根节点下创建。",
    )
    def post(self, request, scope: str):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 获取操作人
        actor = _get_tenant_actor(request)
        
        # 4. 校验请求体
        request_serializer = FolderCreateRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            raise GrassAPIException(
                detail="参数校验失败",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_FORMAT",
                data=request_serializer.errors,
            )
        
        parent_node_id = request_serializer.validated_data.get("parent_node_id")
        name = request_serializer.validated_data["name"]
        
        # 5. 调用服务层创建文件夹
        folder = create_folder(
            tenant_id=tenant_id,
            scope=scope_upper,
            parent_node_id=parent_node_id,
            name=name,
            actor=actor,
        )
        
        # 6. 转换为 DTO
        folder_dto = _node_to_dto(folder)
        
        # 7. 返回响应
        return envelope_response(
            data={"node": folder_dto},
            request=request,
        )


class ChildrenView(APIView):
    """
    查询资源树子节点
    
    GET /api/resource-trees/{scope}/children
    
    返回指定节点的子节点列表（含 folders + resources），按 sort_order 排序。
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
            OpenApiParameter(
                name="parent_node_id",
                location=OpenApiParameter.QUERY,
                required=False,
                type=int,
                description="父节点ID，不传则查询根节点的子节点",
            ),
            OpenApiParameter(
                name="include_resources",
                location=OpenApiParameter.QUERY,
                required=False,
                type=int,
                description="是否包含资源节点，0=仅文件夹，1=全部（默认）",
            ),
        ],
        responses={
            200: ChildrenResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="ChildrenError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（非法scope等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="ChildrenError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="ChildrenError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="ChildrenError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="节点不存在",
            ),
        },
        tags=["ResourceTrees"],
        summary="查询子节点",
        description="返回指定节点的子节点列表，按 sort_order 排序。"
                    "如果不传 parent_node_id，则返回根节点的子节点。",
    )
    def get(self, request, scope: str):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文（由 TenantContext 中间件注入）
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 解析查询参数
        query_serializer = ChildrenQuerySerializer(data=request.query_params)
        if not query_serializer.is_valid():
            raise GrassAPIException(
                detail="参数校验失败",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_FORMAT",
                data=query_serializer.errors,
            )
        
        parent_node_id = query_serializer.validated_data.get("parent_node_id")
        include_resources = query_serializer.validated_data.get("include_resources", 1) == 1
        
        # 4. 如果指定了 parent_node_id，校验节点存在且属于当前租户/scope
        if parent_node_id is not None:
            parent_node = get_node_by_id(tenant_id, scope_upper, parent_node_id)
            if parent_node is None:
                raise GrassAPIException(
                    detail=f"节点不存在: {parent_node_id}",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="RESOURCE_NODE_NOT_FOUND",
                )
        else:
            # 确保根节点存在
            root_node = get_root_node(tenant_id, scope_upper)
            if root_node is None:
                # 根节点不存在，返回空列表
                return envelope_response(
                    data={"items": []},
                    request=request,
                )
        
        # 5. 查询子节点
        children = list_children(
            tenant_id=tenant_id,
            scope=scope_upper,
            parent_node_id=parent_node_id,
            include_resources=include_resources,
        )
        
        # 6. 转换为 DTO
        items = [_node_to_dto(node) for node in children]
        
        # 7. 返回响应
        return envelope_response(
            data={"items": items},
            request=request,
        )


def _get_tenant_actor(request):
    """
    从 request 获取 tenant_user（操作人）
    
    Args:
        request: DRF request 对象
    
    Returns:
        TenantUser 对象
    
    Raises:
        GrassAPIException: 如果缺少租户上下文
    """
    tenant_user = getattr(request, "tenant_user", None)
    if tenant_user is None:
        raise GrassAPIException(
            detail="缺少租户上下文",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )
    return tenant_user


class RenameNodeView(APIView):
    """
    重命名资源树节点
    
    PATCH /api/resource-trees/{scope}/nodes/{node_id}
    
    对照 tech.md §6.2.5.3:
    - 重命名 folder 或 resource 节点
    - 保持路径/唯一约束
    - 不支持改 scope/type
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                required=True,
                type=int,
                description="节点ID",
            ),
        ],
        request=RenameNodeRequestSerializer,
        responses={
            200: RenameNodeResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="RenameNodeError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（非法scope/名称长度等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="RenameNodeError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="RenameNodeError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="RenameNodeError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="节点不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="RenameNodeError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="名称冲突（同级节点已存在同名）",
            ),
        },
        tags=["ResourceTrees"],
        summary="重命名节点",
        description="重命名 folder 或 resource 节点，并保持路径/唯一约束。"
                    "不支持改 scope/type。",
    )
    def patch(self, request, scope: str, node_id: int):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 获取操作人
        actor = _get_tenant_actor(request)
        
        # 4. 校验请求体
        request_serializer = RenameNodeRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            raise GrassAPIException(
                detail="参数校验失败",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_FORMAT",
                data=request_serializer.errors,
            )
        
        new_name = request_serializer.validated_data["name"]
        
        # 5. 调用服务层重命名节点
        node = rename_node(
            tenant_id=tenant_id,
            scope=scope_upper,
            node_id=node_id,
            new_name=new_name,
            actor=actor,
        )
        
        # 6. 转换为 DTO
        node_dto = _node_to_dto(node)
        
        # 7. 返回响应
        return envelope_response(
            data={"node": node_dto},
            request=request,
        )


def _get_tenant_actor(request):
    """获取租户操作人（TenantUser）"""
    tenant_user = getattr(request, "tenant_user", None)
    if tenant_user is None:
        raise GrassAPIException(
            detail="缺少租户上下文",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )
    return tenant_user


class NodeDeleteView(APIView):
    """
    删除资源树节点
    
    DELETE /api/resource-trees/{scope}/nodes/{node_id}
    
    对照 tech.md §6.2.5.6:
    - 删除 folder：必须为空，否则 FOLDER_NOT_EMPTY
    - 删除 resource node：仅解除挂载（不删除资源对象本身）
    - root 节点不可删除
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                required=True,
                type=int,
                description="节点ID",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeResponse200",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": inline_serializer(
                            name="DeleteNodeData",
                            fields={
                                "deleted": serializers.BooleanField(),
                            },
                        ),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="删除成功",
            ),
            400: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（根节点不可删等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="节点不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="DeleteNodeError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="文件夹不为空",
            ),
        },
        tags=["ResourceTrees"],
        summary="删除节点",
        description="删除资源树节点。删除 folder 必须为空；删除 resource node 仅解除挂载。",
    )
    def delete(self, request, scope: str, node_id: int):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 获取操作人
        actor = _get_tenant_actor(request)
        
        # 4. 调用服务层删除节点
        # TODO: 实现 delete_node 服务函数（任务 T4.7）
        raise GrassAPIException(
            detail="删除节点功能尚未实现",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="NOT_IMPLEMENTED",
        )
        
        # 5. 返回响应
        return envelope_response(
            data={"deleted": True},
            request=request,
        )


class ReorderView(APIView):
    """
    同级排序：重排同一父节点下的节点顺序
    
    POST /api/resource-trees/{scope}/reorder
    
    对照 tech.md §6.2.5.5:
    - 同一 parent 下按给定序列重排节点顺序
    - 输入校验（同级节点全集/不缺不重）
    - 批量更新 order
    - 审计：NODE_REORDER
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
        ],
        request=ReorderRequestSerializer,
        responses={
            200: ReorderResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="ReorderError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（缺失id/重复id/节点不匹配等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="ReorderError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="ReorderError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="ReorderError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="父节点不存在",
            ),
        },
        tags=["ResourceTrees"],
        summary="同级排序",
        description="同一 parent 下按给定序列重排节点顺序。"
                    "ordered_node_ids 必须包含该 parent 下全部子节点，不缺不重。",
    )
    def post(self, request, scope: str):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 获取操作人
        actor = _get_tenant_actor(request)
        
        # 4. 解析请求体
        request_serializer = ReorderRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            raise GrassAPIException(
                detail="参数校验失败",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_FORMAT",
                data=request_serializer.errors,
            )
        
        parent_node_id = request_serializer.validated_data.get("parent_node_id")
        ordered_node_ids = request_serializer.validated_data["ordered_node_ids"]
        
        # 5. 调用服务层重排序节点
        # TODO: 实现 reorder_nodes 服务函数（任务 T4.6）
        raise GrassAPIException(
            detail="节点排序功能尚未实现",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="NOT_IMPLEMENTED",
        )


class MoveNodeView(APIView):
    """
    移动节点：将节点移动到新的父节点
    
    POST /api/resource-trees/{scope}/move
    
    对照 tech.md §6.2.5.4:
    - 校验 src/dst
    - 防循环（不能移入自身子树）
    - 更新 parent_node_id/order
    - 审计：NODE_MOVE（TODO：等审计模块实现后补充）
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                enum=[s.value for s in ResourceScope],
                description="资源域（TABLE/FLOW/DATASET/DASHBOARD）",
            ),
        ],
        request=MoveNodeRequestSerializer,
        responses={
            200: MoveNodeResponseEnvelopeSerializer,
            400: OpenApiResponse(
                response=inline_serializer(
                    name="MoveNodeError400",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="参数校验失败（非法移动/循环等）",
            ),
            401: OpenApiResponse(
                response=inline_serializer(
                    name="MoveNodeError401",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="未认证",
            ),
            403: OpenApiResponse(
                response=inline_serializer(
                    name="MoveNodeError403",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="无权限访问",
            ),
            404: OpenApiResponse(
                response=inline_serializer(
                    name="MoveNodeError404",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="节点不存在",
            ),
            409: OpenApiResponse(
                response=inline_serializer(
                    name="MoveNodeError409",
                    fields={
                        "code": serializers.CharField(),
                        "message": serializers.CharField(),
                        "data": serializers.JSONField(required=False),
                        "request_id": serializers.CharField(),
                    },
                ),
                description="节点冲突",
            ),
        },
        tags=["ResourceTrees"],
        summary="移动节点",
        description="将节点移动到新的父节点，并维护 order 与路径。"
                    "不能移入自身子树。",
    )
    def post(self, request, scope: str):
        # 1. 校验 scope 是否有效
        scope_upper = scope.upper()
        if not is_valid_scope(scope_upper):
            raise GrassAPIException(
                detail=f"无效的 scope: {scope}，有效值为 TABLE/FLOW/DATASET/DASHBOARD",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SCOPE",
            )
        
        # 2. 校验租户上下文
        if not hasattr(request, "tenant_id") or request.tenant_id is None:
            raise GrassAPIException(
                detail="缺少租户上下文",
                status_code=status.HTTP_403_FORBIDDEN,
                code=ErrorCode.PERMISSION_DENIED,
            )
        
        tenant_id = request.tenant_id
        
        # 3. 获取操作人
        actor = _get_tenant_actor(request)
        
        # 4. 解析请求体
        request_serializer = MoveNodeRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            raise GrassAPIException(
                detail="参数校验失败",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_FORMAT",
                data=request_serializer.errors,
            )
        
        node_id = request_serializer.validated_data["node_id"]
        target_parent_node_id = request_serializer.validated_data.get("target_parent_node_id")
        target_index = request_serializer.validated_data.get("target_index")
        
        # 5. 调用服务层移动节点
        move_node(
            tenant_id=tenant_id,
            scope=scope_upper,
            node_id=node_id,
            target_parent_node_id=target_parent_node_id,
            target_index=target_index,
            actor=actor,
        )
        
        # 6. 返回响应
        return envelope_response(
            data={"moved": True},
            request=request,
        )
