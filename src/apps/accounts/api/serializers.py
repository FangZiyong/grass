"""
Auth API Serializers
"""
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    """登录请求序列化器"""

    login_name = serializers.CharField(min_length=1, max_length=64)
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False)


class LoginUserSerializer(serializers.Serializer):
    """登录响应中的用户信息"""

    user_id = serializers.IntegerField()
    login_name = serializers.CharField()
    display_name = serializers.CharField()
    email = serializers.EmailField()
    is_platform_admin = serializers.BooleanField()
    last_tenant_id = serializers.IntegerField(required=False, allow_null=True)


class LoginTenantSerializer(serializers.Serializer):
    """登录响应中的租户信息"""

    tenant_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    plan = serializers.CharField()


class LoginResponseDataSerializer(serializers.Serializer):
    """登录响应 data"""

    access_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    user = LoginUserSerializer()
    tenant = LoginTenantSerializer(required=False)


class LoginResponseEnvelopeSerializer(serializers.Serializer):
    """登录响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = LoginResponseDataSerializer()
    request_id = serializers.CharField()


class RefreshResponseDataSerializer(serializers.Serializer):
    """刷新响应 data"""

    access_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    user = LoginUserSerializer()


class RefreshResponseEnvelopeSerializer(serializers.Serializer):
    """刷新响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = RefreshResponseDataSerializer()
    request_id = serializers.CharField()


class LogoutResponseDataSerializer(serializers.Serializer):
    """登出响应 data（空对象）"""

    pass


class LogoutResponseEnvelopeSerializer(serializers.Serializer):
    """登出响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = LogoutResponseDataSerializer()
    request_id = serializers.CharField()


class MeUserSerializer(serializers.Serializer):
    """我的信息中的用户字段"""

    user_id = serializers.IntegerField()
    login_name = serializers.CharField()
    display_name = serializers.CharField()
    email = serializers.EmailField()
    is_platform_admin = serializers.BooleanField()
    status = serializers.CharField()
    last_tenant_id = serializers.IntegerField(required=False, allow_null=True)


class MeTenantSerializer(serializers.Serializer):
    """我的信息中的租户字段"""

    tenant_id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    plan = serializers.CharField()


class MeResponseDataSerializer(serializers.Serializer):
    """我的信息响应 data"""

    user = MeUserSerializer()
    tenant = MeTenantSerializer(required=False)


class MeResponseEnvelopeSerializer(serializers.Serializer):
    """我的信息响应统一壳"""

    code = serializers.CharField()
    message = serializers.CharField()
    data = MeResponseDataSerializer()
    request_id = serializers.CharField()
