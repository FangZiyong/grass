"""
resource_tree API 序列化器

对照 tech.md §6.2.5.1 ResourceTreeNodeDTO 定义。
"""
from rest_framework import serializers


class ResourceTreeNodeSerializer(serializers.Serializer):
    """
    资源树节点 DTO
    
    对照 tech.md ResourceTreeNodeDTO:
    - node_id: int64
    - scope: string (TABLE/FLOW/DATASET/DASHBOARD)
    - node_type: string (FOLDER/RESOURCE)
    - parent_node_id: int64|null
    - name: string
    - order_index: int
    - resource_type: string|null
    - resource_id: int64|null
    """
    
    node_id = serializers.IntegerField(help_text="节点ID")
    scope = serializers.CharField(help_text="资源域（TABLE/FLOW/DATASET/DASHBOARD）")
    node_type = serializers.CharField(help_text="节点类型（FOLDER/RESOURCE）")
    parent_node_id = serializers.IntegerField(
        allow_null=True,
        help_text="父节点ID，根节点为null"
    )
    name = serializers.CharField(help_text="节点名称")
    order_index = serializers.IntegerField(help_text="排序索引")
    resource_type = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="资源类型（仅 node_type=RESOURCE 时存在）"
    )
    resource_id = serializers.IntegerField(
        allow_null=True,
        required=False,
        help_text="资源ID（仅 node_type=RESOURCE 时存在）"
    )


class ChildrenQuerySerializer(serializers.Serializer):
    """
    查询子节点请求参数序列化器
    
    对照 tech.md §6.2.5.1:
    - parent_node_id: int64（可选；不传/为 null=根）
    - include_resources: int（可选，0/1，默认 1；=0 仅返回 folder）
    """
    
    parent_node_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="父节点ID，不传或为空则查询根节点的子节点"
    )
    include_resources = serializers.IntegerField(
        required=False,
        default=1,
        min_value=0,
        max_value=1,
        help_text="是否包含资源节点，0=仅文件夹，1=全部（默认）"
    )


class ChildrenResponseDataSerializer(serializers.Serializer):
    """
    查询子节点响应 data
    """
    
    items = ResourceTreeNodeSerializer(many=True, help_text="子节点列表")


class ChildrenResponseEnvelopeSerializer(serializers.Serializer):
    """
    查询子节点响应统一壳
    """
    
    code = serializers.CharField()
    message = serializers.CharField()
    data = ChildrenResponseDataSerializer()
    request_id = serializers.CharField()
