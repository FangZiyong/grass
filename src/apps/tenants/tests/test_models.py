"""
tenants 模型测试
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.tenants.models.tenant import Tenant, TenantPlan, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class TenantsModelsTest(TestCase):
    """tenants 模型测试"""

    def test_create_tenant(self):
        """测试创建 Tenant"""
        tenant = Tenant.objects.create(
            code="tenant-a",
            name="租户A",
            status=TenantStatus.ACTIVE,
        )

        self.assertIsNotNone(tenant.tenant_id)
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.plan, TenantPlan.BASIC)

    def test_create_tenant_user(self):
        """测试创建 TenantUser"""
        tenant = Tenant.objects.create(
            code="tenant-b",
            name="租户B",
            status=TenantStatus.ACTIVE,
        )
        tenant_user = TenantUser.objects.create(
            tenant=tenant,
            user_id=1,
            status=TenantUserStatus.ACTIVE,
        )

        self.assertIsNotNone(tenant_user.tenant_user_id)
        self.assertEqual(tenant_user.tenant_id, tenant.tenant_id)
        self.assertEqual(tenant_user.status, TenantUserStatus.ACTIVE)
        self.assertFalse(tenant_user.is_owner)

    def test_unique_tenant_user(self):
        """测试 tenant_id + user_id 唯一约束"""
        tenant = Tenant.objects.create(
            code="tenant-c",
            name="租户C",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=2,
            status=TenantUserStatus.ACTIVE,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TenantUser.objects.create(
                    tenant=tenant,
                    user_id=2,
                    status=TenantUserStatus.ACTIVE,
                )
