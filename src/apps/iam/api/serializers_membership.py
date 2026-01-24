"""
成员-角色绑定 API Serializers
"""
from rest_framework import serializers

from apps.iam.models.roles import Role


class MemberRoleBindRequestSerializer(serializers.Serializer):
    role_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_role_ids(self, value: list[int]) -> list[int]:
        if len(value) > 200:
            raise serializers.ValidationError("最多允许绑定 200 个角色")
        return value


class MemberRoleBindResponseSerializer(serializers.Serializer):
    role_ids = serializers.ListField(child=serializers.IntegerField())


class MemberRoleBindEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = MemberRoleBindResponseSerializer()
    request_id = serializers.CharField()


class MemberRoleUnbindResponseSerializer(serializers.Serializer):
    deleted = serializers.BooleanField()


class MemberRoleUnbindEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = MemberRoleUnbindResponseSerializer()
    request_id = serializers.CharField()


class RoleSummarySerializer(serializers.ModelSerializer):
    """角色简要信息"""

    class Meta:
        model = Role
        fields = ["role_id", "name", "description", "created_at"]
        read_only_fields = fields


class TenantUserSummarySerializer(serializers.Serializer):
    tenant_user_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    email = serializers.EmailField()
    display_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RoleUsersListDataSerializer(serializers.Serializer):
    items = TenantUserSummarySerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total = serializers.IntegerField()


class RoleUsersListEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = RoleUsersListDataSerializer()
    request_id = serializers.CharField()


class MemberRolesResponseSerializer(serializers.Serializer):
    roles = RoleSummarySerializer(many=True)


class MemberRolesEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = MemberRolesResponseSerializer()
    request_id = serializers.CharField()


class OwnerSetResponseSerializer(serializers.Serializer):
    is_owner = serializers.BooleanField()


class OwnerSetEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = OwnerSetResponseSerializer()
    request_id = serializers.CharField()


class OwnerUnsetResponseSerializer(serializers.Serializer):
    is_owner = serializers.BooleanField()


class OwnerUnsetEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = OwnerUnsetResponseSerializer()
    request_id = serializers.CharField()

