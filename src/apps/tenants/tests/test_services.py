"""
Tenant services 测试
"""
from django.test import TestCase

from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus
from apps.tenants.services import switch_tenant
from common.errors.exceptions import GrassAPIException


class TenantServicesTest(TestCase):
    """Tenant services 测试"""
    
    def setUp(self):
        """设置测试数据"""
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
        
        self.user_id = 1
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant_active,
            user_id=self.user_id,
            status=TenantUserStatus.ACTIVE,
        )
    
    def test_switch_tenant_success(self):
        """测试成功切换租户"""
        result = switch_tenant(self.user_id, self.tenant_active.id)
        
        self.assertEqual(result["tenant_id"], self.tenant_active.id)
        self.assertIn("redirect_url", result)
    
    def test_switch_tenant_not_found(self):
        """测试租户不存在"""
        with self.assertRaises(GrassAPIException) as cm:
            switch_tenant(self.user_id, 99999)
        
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(str(cm.exception.error_code), "NOT_FOUND")
    
    def test_switch_tenant_suspended(self):
        """测试切换到 SUSPENDED 租户"""
        TenantUser.objects.create(
            tenant=self.tenant_suspended,
            user_id=self.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        
        with self.assertRaises(GrassAPIException) as cm:
            switch_tenant(self.user_id, self.tenant_suspended.id)
        
        self.assertEqual(cm.exception.status_code, 403)
        self.assertEqual(str(cm.exception.error_code), "PERMISSION_DENIED")
    
    def test_switch_tenant_user_not_in_tenant(self):
        """测试用户不属于该租户"""
        with self.assertRaises(GrassAPIException) as cm:
            switch_tenant(999, self.tenant_active.id)
        
        self.assertEqual(cm.exception.status_code, 403)
        self.assertEqual(str(cm.exception.error_code), "PERMISSION_DENIED")
    
    def test_switch_tenant_user_disabled(self):
        """测试用户在该租户中已被禁用"""
        disabled_user_id = 2
        TenantUser.objects.create(
            tenant=self.tenant_active,
            user_id=disabled_user_id,
            status=TenantUserStatus.DISABLED,
        )
        
        with self.assertRaises(GrassAPIException) as cm:
            switch_tenant(disabled_user_id, self.tenant_active.id)
        
        self.assertEqual(cm.exception.status_code, 403)
        self.assertEqual(str(cm.exception.error_code), "PERMISSION_DENIED")

