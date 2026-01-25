"""
IAM 权限相关序列化器（角色资源授权 / 权限面板）
"""
from rest_framework import serializers

from apps.iam.models.grants import PermissionLevel, ResourceType
from apps.resource_tree.models.resource_node import ResourceScope

_RESOURCE_SCOPES = ResourceScope.choices

_SCOPE_RESOURCE_TYPE = {
    ResourceScope.FLOW: ResourceType.FLOW,
    ResourceScope.DATASET: ResourceType.DATASET,
    ResourceScope.DASHBOARD: ResourceType.DASHBOARD,
}


class RolePermissionItemSerializer(serializers.Serializer):
    grant_id = serializers.IntegerField()
    resource_tree_node_id = serializers.IntegerField()
    resource_type = serializers.ChoiceField(choices=ResourceType.choices)
    permission_level = serializers.ChoiceField(choices=PermissionLevel.choices)
    is_inherited = serializers.BooleanField()


class RoleResourcePermissionsDataSerializer(serializers.Serializer):
    items = RolePermissionItemSerializer(many=True)


class RoleResourcePermissionsEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RoleResourcePermissionsDataSerializer()
    request_id = serializers.CharField()


class RolePermissionSaveItemSerializer(serializers.Serializer):
    resource_tree_node_id = serializers.IntegerField()
    resource_type = serializers.ChoiceField(choices=ResourceType.choices)
    permission_level = serializers.ChoiceField(choices=PermissionLevel.choices)


class SaveRoleResourcePermissionsRequestSerializer(serializers.Serializer):
    items = RolePermissionSaveItemSerializer(many=True)

    def validate_items(self, value):
        seen = set()
        for item in value:
            key = (item["resource_type"], item["resource_tree_node_id"])
            if key in seen:
                raise serializers.ValidationError("resource_type 与 resource_tree_node_id 组合重复")
            seen.add(key)
        return value


class SaveRoleResourcePermissionsDataSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class SaveRoleResourcePermissionsEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = SaveRoleResourcePermissionsDataSerializer()
    request_id = serializers.CharField()


class PermissionPanelQuerySerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=_RESOURCE_SCOPES)
    resource_type = serializers.ChoiceField(choices=ResourceType.choices, required=False)

    def validate(self, attrs):
        scope = attrs.get("scope")
        resource_type = attrs.get("resource_type")
        if scope == ResourceScope.TABLE:
            if not resource_type:
                raise serializers.ValidationError("TABLE scope 必须提供 resource_type")
            if resource_type not in (ResourceType.TABLE_SCHEMA, ResourceType.TABLE_DATA):
                raise serializers.ValidationError("TABLE scope 仅支持 TABLE_SCHEMA 或 TABLE_DATA")
        else:
            expected = _SCOPE_RESOURCE_TYPE.get(scope)
            if resource_type and expected and resource_type != expected:
                raise serializers.ValidationError("resource_type 与 scope 不匹配")
            attrs["resource_type"] = expected
        return attrs


class RoleGrantItemSerializer(serializers.Serializer):
    grant_id = serializers.IntegerField()
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()
    permission_level = serializers.ChoiceField(choices=PermissionLevel.choices)


class PermissionPanelDataSerializer(serializers.Serializer):
    resource_node_id = serializers.IntegerField()
    role_grants = RoleGrantItemSerializer(many=True)
    my_effective_permission = serializers.ChoiceField(choices=PermissionLevel.choices)
    can_manage = serializers.BooleanField()


class PermissionPanelEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = PermissionPanelDataSerializer()
    request_id = serializers.CharField()


# ======== 授权接口序列化器 ========


class UpsertGrantRequestSerializer(serializers.Serializer):
    """
    POST /api/permissions/grants 请求体序列化器

    字段说明：
    - scope: 资源树作用域（TABLE/FLOW/DATASET/DASHBOARD）
    - resource_type: 资源类型，TABLE scope 必填，其他 scope 自动映射
    - resource_tree_node_id: 资源树节点 ID
    - role_id: 角色 ID
    - permission_level: 权限等级（NONE 时视为删除）
    """

    scope = serializers.ChoiceField(
        choices=_RESOURCE_SCOPES,
        help_text="资源树作用域：TABLE/FLOW/DATASET/DASHBOARD",
    )
    resource_type = serializers.ChoiceField(
        choices=ResourceType.choices,
        required=False,
        help_text="资源类型，TABLE scope 时必填（TABLE_SCHEMA/TABLE_DATA）",
    )
    resource_tree_node_id = serializers.IntegerField(
        help_text="资源树节点 ID",
    )
    role_id = serializers.IntegerField(
        help_text="角色 ID",
    )
    permission_level = serializers.ChoiceField(
        choices=PermissionLevel.choices,
        help_text="权限等级：NONE/VIEW/EDIT/MANAGE，NONE 时视为删除",
    )

    def validate(self, attrs):
        """
        验证 scope 与 resource_type 的匹配关系：
        - TABLE scope 必须显式提供 resource_type（TABLE_SCHEMA 或 TABLE_DATA）
        - 其他 scope 自动映射对应的 resource_type
        """
        scope = attrs.get("scope")
        resource_type = attrs.get("resource_type")
        if scope == ResourceScope.TABLE:
            # TABLE scope 必须显式指定 resource_type
            if not resource_type:
                raise serializers.ValidationError("TABLE scope 必须提供 resource_type")
            if resource_type not in (ResourceType.TABLE_SCHEMA, ResourceType.TABLE_DATA):
                raise serializers.ValidationError("TABLE scope 仅支持 TABLE_SCHEMA 或 TABLE_DATA")
        else:
            # 非 TABLE scope，自动映射 resource_type（如 FLOW -> FLOW）
            expected = _SCOPE_RESOURCE_TYPE.get(scope)
            if resource_type and expected and resource_type != expected:
                raise serializers.ValidationError("resource_type 与 scope 不匹配")
            attrs["resource_type"] = expected
        return attrs


class UpsertGrantDataSerializer(serializers.Serializer):
    """POST /api/permissions/grants 响应 data"""

    grant_id = serializers.IntegerField()


class UpsertGrantEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = UpsertGrantDataSerializer()
    request_id = serializers.CharField()


class RevokeGrantDataSerializer(serializers.Serializer):
    """DELETE /api/permissions/grants/{grant_id} 响应 data"""

    deleted = serializers.BooleanField()


class RevokeGrantEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RevokeGrantDataSerializer()
    request_id = serializers.CharField()

