"""
Role API Serializers
"""
import re

from rest_framework import serializers

from apps.iam.models.roles import Role, RoleStatus


class RoleSerializer(serializers.ModelSerializer):
    """角色 DTO"""

    class Meta:
        model = Role
        fields = [
            "role_id",
            "tenant_id",
            "code",
            "name",
            "description",
            "is_builtin",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RoleListQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=RoleStatus.choices,
        required=False,
    )


class RoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("角色名称长度至少为2")
        return value.strip()


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=64)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.ChoiceField(choices=RoleStatus.choices, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("至少提供一个字段进行更新")
        if "name" in attrs:
            attrs["name"] = attrs["name"].strip()
            if len(attrs["name"]) < 2:
                raise serializers.ValidationError("角色名称长度至少为2")
        return attrs


class RoleListDataSerializer(serializers.Serializer):
    items = RoleSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total = serializers.IntegerField()


class RoleListEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RoleListDataSerializer()
    request_id = serializers.CharField()


class RoleResponseSerializer(serializers.Serializer):
    role = RoleSerializer()


class RoleEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RoleResponseSerializer()
    request_id = serializers.CharField()


class RoleDeleteResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()


class RoleDeleteEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RoleDeleteResponseSerializer()
    request_id = serializers.CharField()
