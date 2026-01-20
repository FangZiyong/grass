"""
TenantContext 中间件测试

根据 T0.5 验收标准：
- ✅ 单测覆盖：至少 6 个分支（header/last_tenant；无成员；suspended；正常；未登录；错误 tenant_id）
"""
import json

from django.http import HttpResponse
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus
from common.middleware.auth_context import AuthContextUser
from common.middleware.tenant_context import TenantContextMiddleware


class TenantContextMiddlewareTest(TestCase):
    """TenantContext 中间件测试"""
    
    def setUp(self):
        """设置测试数据"""
        self.factory = APIRequestFactory()
        
        # 创建测试租户
        self.tenant_active = Tenant.objects.create(
            code="test-tenant",
            name="测试租户",
            status=TenantStatus.ACTIVE,
        )
        self.tenant_suspended = Tenant.objects.create(
            code="suspended-tenant",
            name="已停用租户",
            status=TenantStatus.SUSPENDED,
        )
        
        # 创建测试用户ID（模拟）
        self.user_id = 1
        self.other_user_id = 2
        
        # 创建租户成员
        self.tenant_user_active = TenantUser.objects.create(
            tenant=self.tenant_active,
            user_id=self.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        self.tenant_user_disabled = TenantUser.objects.create(
            tenant=self.tenant_active,
            user_id=self.other_user_id,
            status=TenantUserStatus.DISABLED,
        )
    
    def _create_middleware(self):
        """创建中间件实例"""
        def get_response(request):
            return HttpResponse("OK")
        return TenantContextMiddleware(get_response)
    
    def _create_request(self, path="/api/test", tenant_id=None, user=None):
        """创建测试请求"""
        request = self.factory.get(path)
        if tenant_id is not None:
            request.META["HTTP_X_TENANT_ID"] = str(tenant_id)
        if user is not None:
            request.user = user
        return request
    
    def test_public_path_no_tenant_required(self):
        """测试公开路径不需要租户上下文"""
        middleware = self._create_middleware()
        request = self._create_request(path="/api/auth/login")
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(hasattr(request, "tenant"))
    
    def test_admin_path_no_tenant_required(self):
        """测试平台后台路径不需要租户上下文"""
        middleware = self._create_middleware()
        request = self._create_request(path="/admin/api/users")
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(hasattr(request, "tenant"))
    
    def test_missing_tenant_id_header(self):
        """测试缺少 X-Tenant-Id header"""
        middleware = self._create_middleware()
        request = self._create_request(path="/api/modeling/tables")
        request.user = AuthContextUser(user_id=self.user_id)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("X-Tenant-Id", data["message"])
    
    def test_invalid_tenant_id(self):
        """测试无效的 tenant_id（不存在）"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=99999,
        )
        request.user = AuthContextUser(user_id=self.user_id)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "NOT_FOUND")
        self.assertIn("租户不存在", data["message"])
    
    def test_suspended_tenant(self):
        """测试 SUSPENDED 租户返回 403"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=self.tenant_suspended.id,
        )
        request.user = AuthContextUser(user_id=self.user_id)
        
        # 创建该用户在停用租户中的成员关系
        TenantUser.objects.create(
            tenant=self.tenant_suspended,
            user_id=self.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "PERMISSION_DENIED")
        self.assertIn("租户已停用", data["message"])
    
    def test_user_not_in_tenant(self):
        """测试用户不属于该租户"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=self.tenant_active.id,
        )
        # 使用一个不属于该租户的用户
        request.user = AuthContextUser(user_id=999)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "PERMISSION_DENIED")
        self.assertIn("用户不属于该租户", data["message"])
    
    def test_user_disabled_in_tenant(self):
        """测试用户在该租户中已被禁用"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=self.tenant_active.id,
        )
        request.user = AuthContextUser(user_id=self.other_user_id)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "PERMISSION_DENIED")
        self.assertIn("用户在该租户中已被禁用", data["message"])
    
    def test_unauthenticated_user(self):
        """测试未登录用户"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=self.tenant_active.id,
        )
        # 不设置 request.user
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "UNAUTHENTICATED")
    
    def test_success_with_valid_tenant(self):
        """测试正常情况：有效的租户和用户"""
        middleware = self._create_middleware()
        request = self._create_request(
            path="/api/modeling/tables",
            tenant_id=self.tenant_active.id,
        )
        request.user = AuthContextUser(user_id=self.user_id)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(request, "tenant"))
        self.assertEqual(request.tenant.id, self.tenant_active.id)
        self.assertTrue(hasattr(request, "tenant_id"))
        self.assertEqual(request.tenant_id, self.tenant_active.id)
        self.assertTrue(hasattr(request, "tenant_user"))
        self.assertEqual(request.tenant_user.id, self.tenant_user_active.id)
    
    def test_invalid_tenant_id_format(self):
        """测试 tenant_id 格式错误（非数字）"""
        middleware = self._create_middleware()
        request = self._create_request(path="/api/modeling/tables")
        request.META["HTTP_X_TENANT_ID"] = "invalid"
        request.user = AuthContextUser(user_id=self.user_id)
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("X-Tenant-Id", data["message"])

