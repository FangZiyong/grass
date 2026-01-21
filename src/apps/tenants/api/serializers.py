"""
Tenant API Serializers

根据 tech.md §4.7.3 和 architecture.md：
- GET /api/tenants：租户列表
- POST /api/tenants/switch：切换租户
"""
from rest_framework import serializers

from apps.tenants.models.tenant import Tenant, TenantPlan, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class TenantBriefSerializer(serializers.ModelSerializer):
    """租户简要信息序列化器（用于列表）"""

    is_recent = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ["tenant_id", "code", "name", "status", "is_recent"]
        read_only_fields = ["tenant_id", "code", "name", "status", "is_recent"]

    def get_is_recent(self, obj) -> bool:
        recent_tenant_id = self.context.get("recent_tenant_id")
        if not recent_tenant_id:
            return False
        return obj.tenant_id == recent_tenant_id


class TenantSwitchSerializer(serializers.Serializer):
    """切换租户请求序列化器"""
    
    tenant_id = serializers.IntegerField(help_text="目标租户ID")
    
    def validate_tenant_id(self, value):
        """校验 tenant_id 必须大于0"""
        if value <= 0:
            raise serializers.ValidationError("tenant_id 必须大于0")
        return value


class TenantSwitchResponseSerializer(serializers.Serializer):
    """切换租户响应序列化器"""
    
    tenant_id = serializers.IntegerField(help_text="切换成功的租户ID")
    redirect_url = serializers.CharField(help_text="前端跳转地址")


class TenantListDataSerializer(serializers.Serializer):
    """租户列表响应 data"""

    items = TenantBriefSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total = serializers.IntegerField()


class TenantListEnvelopeSerializer(serializers.Serializer):
    """租户列表响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = TenantListDataSerializer()
    request_id = serializers.CharField()


class TenantSwitchEnvelopeSerializer(serializers.Serializer):
    """切换租户响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = TenantSwitchResponseSerializer()
    request_id = serializers.CharField()

