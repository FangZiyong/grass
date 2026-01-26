"""
resource_tree API 序列化器

对照 tech.md §6.2.5.1 ResourceTreeNodeDTO 定义。
"""
from rest_framework import serializers

from common.http import create_envelope_serializer


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


class RenameNodeRequestSerializer(serializers.Serializer):
    """
    重命名节点请求序列化器
    
    对照 tech.md §6.2.5.3:
    - name: string（必填，1~64）
    """
    
    name = serializers.CharField(
        min_length=1,
        max_length=64,
        help_text="新节点名称（1~64字符）"
    )


class RenameNodeResponseDataSerializer(serializers.Serializer):
    """
    重命名节点响应 data
    """
    
    node = ResourceTreeNodeSerializer(help_text="更新后的节点")


class RenameNodeResponseEnvelopeSerializer(serializers.Serializer):
    """
    重命名节点响应统一壳
    """
    
    code = serializers.CharField()
    message = serializers.CharField()
    data = RenameNodeResponseDataSerializer()
    request_id = serializers.CharField()


class ReorderRequestSerializer(serializers.Serializer):
    """
    同级排序请求序列化器
    
    对照 tech.md §6.2.5.5:
    - parent_node_id?: int64（可选；不传/为 null=根）
    - ordered_node_ids: int64[]（必填；必须包含该 parent 下全部子节点）
    """
    
    parent_node_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="父节点ID，不传或为空则对根节点的子节点排序"
    )
    ordered_node_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=0,
        help_text="有序的节点ID列表，必须包含该parent下全部子节点"
    )


class ReorderResponseDataSerializer(serializers.Serializer):
    """
    同级排序响应 data
    
    对照 tech.md §6.2.5.5:
    - updated: int
    """
    
    updated = serializers.IntegerField(help_text="更新的节点数量")


class ReorderResponseEnvelopeSerializer(serializers.Serializer):
    """
    同级排序响应统一壳
    """
    
    code = serializers.CharField()
    message = serializers.CharField()
    data = ReorderResponseDataSerializer()
    request_id = serializers.CharField()


class MoveNodeRequestSerializer(serializers.Serializer):
    """
    移动节点请求序列化器
    
    对照 tech.md §6.2.5.4:
    - node_id: int64（必填）
    - target_parent_node_id: int64|null（必填；允许移动到根）
    - target_index?: int（可选；不传则追加到末尾）
    """
    
    node_id = serializers.IntegerField(
        help_text="要移动的节点ID"
    )
    target_parent_node_id = serializers.IntegerField(
        allow_null=True,
        help_text="目标父节点ID，null表示移动到根节点"
    )
    target_index = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        help_text="目标位置索引（可选；不传则追加到末尾）"
    )


class MoveNodeResponseDataSerializer(serializers.Serializer):
    """
    移动节点响应 data
    
    对照 tech.md §6.2.5.4:
    - moved: bool
    """
    
    moved = serializers.BooleanField(help_text="是否移动成功")


# 使用全局统一响应壳序列化器
MoveNodeResponseEnvelopeSerializer = create_envelope_serializer(MoveNodeResponseDataSerializer)


class FolderCreateRequestSerializer(serializers.Serializer):
    """
    创建文件夹请求序列化器
    
    对照 tech.md §6.2.5.2:
    - parent_node_id: int64|null（可选；不传/为 null=根）
    - name: string（必填，1~64）
    """
    
    parent_node_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="父节点ID，不传或为空则在根节点下创建"
    )
    name = serializers.CharField(
        min_length=1,
        max_length=64,
        help_text="文件夹名称（1~64字符）"
    )


class FolderCreateResponseDataSerializer(serializers.Serializer):
    """
    创建文件夹响应 data
    
    对照 tech.md §6.2.5.2:
    - node: ResourceTreeNodeDTO
    """
    
    node = ResourceTreeNodeSerializer(help_text="创建的文件夹节点")


class FolderCreateResponseEnvelopeSerializer(serializers.Serializer):
    """
    创建文件夹响应统一壳
    """
    
    code = serializers.CharField()
    message = serializers.CharField()
    data = FolderCreateResponseDataSerializer()
    request_id = serializers.CharField()
