"""
我的信息接口测试：GET /api/me
"""
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.accounts.services.tokens import issue_access_token
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class MeAPITest(TestCase):
    """我的信息接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = GlobalUser.objects.create(
            login_name="me_user",
            display_name="Me User",
            email="me_user@example.com",
            password_hash=make_password("Password123!"),
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=False,
        )
        self.token, _ = issue_access_token(
            user_id=self.user.user_id, is_platform_admin=self.user.is_platform_admin
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_me_without_tenant_context(self):
        """不提供 tenant header 也可返回用户信息"""
        self._auth()

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertIn("user", data)
        self.assertNotIn("tenant", data)
        self.assertEqual(data["user"]["user_id"], self.user.user_id)
        self.assertEqual(data["user"]["login_name"], self.user.login_name)
        self.assertEqual(data["user"]["status"], GlobalUserStatus.ACTIVE)

    def test_me_with_tenant_context(self):
        """携带 tenant header 时返回 tenant 上下文"""
        self._auth()
        tenant = Tenant.objects.create(
            code="me-tenant",
            name="Me Tenant",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )

        response = self.client.get("/api/me", HTTP_X_TENANT_ID=str(tenant.tenant_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["tenant_id"], tenant.tenant_id)
        self.assertEqual(data["tenant"]["code"], tenant.code)

    def test_me_with_last_tenant_fallback(self):
        """未携带 tenant header 时回退最近租户"""
        self._auth()
        tenant = Tenant.objects.create(
            code="recent-tenant",
            name="Recent Tenant",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        self.user.last_tenant_id = tenant.tenant_id
        self.user.save(update_fields=["last_tenant_id", "updated_at"])

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["tenant_id"], tenant.tenant_id)

    def test_me_without_header_uses_last_tenant_id(self):
        """不携带 tenant header 时，若 last_tenant_id 存在则返回 tenant 上下文"""
        self._auth()
        tenant = Tenant.objects.create(
            code="me-tenant-last",
            name="Me Tenant Last",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        self.user.last_tenant_id = tenant.tenant_id
        self.user.save(update_fields=["last_tenant_id", "updated_at"])

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["tenant_id"], tenant.tenant_id)
        self.assertEqual(data["tenant"]["code"], tenant.code)

    def test_me_without_header_ignores_suspended_last_tenant(self):
        """最近租户已停用时，不返回 tenant 上下文"""
        self._auth()
        tenant = Tenant.objects.create(
            code="me-tenant-suspended",
            name="Me Tenant Suspended",
            status=TenantStatus.SUSPENDED,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )
        self.user.last_tenant_id = tenant.tenant_id
        self.user.save(update_fields=["last_tenant_id", "updated_at"])

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertNotIn("tenant", data)

    def test_me_without_header_single_tenant_returns_tenant(self):
        """不携带 tenant header 且 last_tenant_id 为空时，若仅有一个可用租户则返回该租户上下文"""
        self._auth()
        tenant = Tenant.objects.create(
            code="me-tenant-only",
            name="Me Tenant Only",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant,
            user_id=self.user.user_id,
            status=TenantUserStatus.ACTIVE,
        )

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["tenant_id"], tenant.tenant_id)
        self.assertEqual(data["tenant"]["code"], tenant.code)

    def test_me_unauthenticated(self):
        """未登录返回 401"""
        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "UNAUTHENTICATED")

    def test_me_user_disabled(self):
        """用户被禁用返回 403"""
        disabled_user = GlobalUser.objects.create(
            login_name="disabled_user",
            display_name="Disabled User",
            email="disabled_user@example.com",
            password_hash=make_password("Password123!"),
            status=GlobalUserStatus.DISABLED,
            is_platform_admin=False,
        )
        token, _ = issue_access_token(
            user_id=disabled_user.user_id, is_platform_admin=disabled_user.is_platform_admin
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "AUTH_USER_DISABLED")
