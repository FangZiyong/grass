"""
resource_tree API 视图

实现资源树相关接口：
- GET /api/resource-trees/{scope}/children - 查询子节点
"""
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated
from apps.resource_tree.api.serializers import (
    ChildrenQuerySerializer,
    ChildrenResponseEnvelopeSerializer,
    ResourceTreeNodeSerializer,
)
from apps.resource_tree.models import ResourceScope
from apps.resource_tree.selectors import (
    get_node_by_id,
    get_root_node,
    is_valid_scope,
    list_children,
)
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
