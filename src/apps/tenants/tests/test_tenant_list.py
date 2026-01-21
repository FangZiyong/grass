"""
租户列表接口测试：GET /api/tenants
"""
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.accounts.services.tokens import issue_access_token
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class TenantListAPITest(TestCase):
    """租户列表接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = GlobalUser.objects.create(
            login_name="tenant_list_user",
            display_name="Tenant List User",
            email="tenant_list_user@example.com",
            password_hash=make_password("Password123!"),
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=False,
        )
        self.token, _ = issue_access_token(
            user_id=self.user.user_id, is_platform_admin=self.user.is_platform_admin
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_tenant_list_success_with_recent(self):
        """正常返回租户列表，包含最近租户标识"""
        tenant_one = Tenant.objects.create(
            code="tenant-one",
            name="Tenant One",
            status=TenantStatus.ACTIVE,
        )
        tenant_two = Tenant.objects.create(
            code="tenant-two",
            name="Tenant Two",
            status=TenantStatus.ACTIVE,
        )
        tenant_suspended = Tenant.objects.create(
            code="tenant-suspended",
            name="Tenant Suspended",
            status=TenantStatus.SUSPENDED,
        )
        TenantUser.objects.create(
            tenant=tenant_one,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant_two,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant_suspended,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        self.user.last_tenant_id = tenant_two.tenant_id
        self.user.save(update_fields=["last_tenant_id", "updated_at"])

        self._auth()
        response = self.client.get("/api/tenants")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 50)
        self.assertEqual(data["total"], 2)

        items_by_id = {item["tenant_id"]: item for item in data["items"]}
        self.assertIn(tenant_one.tenant_id, items_by_id)
        self.assertIn(tenant_two.tenant_id, items_by_id)
        self.assertNotIn(tenant_suspended.tenant_id, items_by_id)

        self.assertTrue(items_by_id[tenant_two.tenant_id]["is_recent"])
        self.assertFalse(items_by_id[tenant_one.tenant_id]["is_recent"])

    def test_tenant_list_empty(self):
        """无租户成员关系返回空列表"""
        self._auth()
        response = self.client.get("/api/tenants")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])

    def test_tenant_list_only_suspended_filtered(self):
        """只有 SUSPENDED 租户时应过滤为空"""
        tenant_suspended = Tenant.objects.create(
            code="tenant-only-suspended",
            name="Tenant Only Suspended",
            status=TenantStatus.SUSPENDED,
        )
        TenantUser.objects.create(
            tenant=tenant_suspended,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )

        self._auth()
        response = self.client.get("/api/tenants")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])

    def test_tenant_list_unauthenticated(self):
        """未登录返回 401"""
        response = self.client.get("/api/tenants")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "UNAUTHENTICATED")
