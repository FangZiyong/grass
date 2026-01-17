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
    
    class Meta:
        model = Tenant
        fields = ["id", "code", "name", "plan", "status"]
        read_only_fields = ["id", "code", "name", "plan", "status"]


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

