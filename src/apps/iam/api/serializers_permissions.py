"""
IAM 权限相关序列化器（角色资源授权 / 权限面板）
"""
from rest_framework import serializers

from apps.iam.models.grants import PermissionLevel, ResourceType

_RESOURCE_SCOPES = (
    ("TABLE", "表"),
    ("FLOW", "流程"),
    ("DATASET", "数据集"),
    ("DASHBOARD", "看板"),
)

_SCOPE_RESOURCE_TYPE = {
    "FLOW": ResourceType.FLOW,
    "DATASET": ResourceType.DATASET,
    "DASHBOARD": ResourceType.DASHBOARD,
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
        if scope == "TABLE":
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


class PermissionsPanelQuerySerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=("TABLE", "FLOW", "DATASET", "DASHBOARD"))
    resource_type = serializers.ChoiceField(
        choices=ResourceType.choices,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        scope = attrs.get("scope")
        resource_type = attrs.get("resource_type")
        if scope == "TABLE" and not resource_type:
            raise serializers.ValidationError("scope=TABLE 时必须传 resource_type")
        return attrs


class RoleGrantItemSerializer(serializers.Serializer):
    grant_id = serializers.IntegerField()
    role_id = serializers.IntegerField()
    role_name = serializers.CharField()
    permission_level = serializers.ChoiceField(choices=PermissionLevel.choices)


class PermissionsPanelDataSerializer(serializers.Serializer):
    resource_node_id = serializers.IntegerField()
    role_grants = RoleGrantItemSerializer(many=True)
    my_effective_permission = serializers.ChoiceField(choices=PermissionLevel.choices)
    can_manage = serializers.BooleanField()


class PermissionsPanelEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = PermissionsPanelDataSerializer()
    request_id = serializers.CharField()

