"""
登录接口测试：POST /api/auth/login
"""
from unittest.mock import patch

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models.sessions import AuthSession, AuthSessionStatus
from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.accounts.services import auth as auth_service
from apps.accounts.services.tokens import generate_refresh_token, hash_refresh_token
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class LoginAPITest(TestCase):
    """登录接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.password_plain = "Password123!"
        self.user = GlobalUser.objects.create(
            login_name="alice",
            display_name="Alice",
            email="alice@example.com",
            password_hash=make_password(self.password_plain),
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=False,
        )

        self.tenant = Tenant.objects.create(
            code="t-one",
            name="Tenant One",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=self.tenant,
            user_id=self.user.id,
            status=TenantUserStatus.ACTIVE,
        )

    def test_login_success_sets_cookie_and_session(self):
        """成功登录：返回 token、写入 session、下发 refresh cookie"""
        response = self.client.post(
            "/api/auth/login",
            {"login_name": self.user.login_name, "password": self.password_plain},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertIn("access_token", data)
        self.assertIn("expires_in", data)
        self.assertIn("user", data)

        cookie = response.cookies.get(auth_service.REFRESH_COOKIE_NAME)
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie.get("httponly"))

        session = AuthSession.objects.get(user_id=self.user.id)
        self.assertEqual(session.status, AuthSessionStatus.ACTIVE)

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login_at)

        # 单租户时返回 tenant
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["id"], self.tenant.id)

    def test_login_invalid_password(self):
        """密码错误"""
        response = self.client.post(
            "/api/auth/login",
            {"login_name": self.user.login_name, "password": "wrong-pass"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_INVALID_CREDENTIALS")

    def test_login_user_disabled(self):
        """用户被禁用"""
        self.user.status = GlobalUserStatus.DISABLED
        self.user.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            "/api/auth/login",
            {"login_name": self.user.login_name, "password": self.password_plain},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "AUTH_USER_DISABLED")

    def test_login_missing_param(self):
        """缺少参数"""
        response = self.client.post(
            "/api/auth/login",
            {"password": self.password_plain},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_REQUIRED")

    def test_login_invalid_format(self):
        """参数格式错误"""
        response = self.client.post(
            "/api/auth/login",
            {"login_name": self.user.login_name, "password": "short"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_FORMAT")

    def test_login_last_tenant(self):
        """多租户下优先返回最近租户"""
        tenant_two = Tenant.objects.create(
            code="t-two",
            name="Tenant Two",
            status=TenantStatus.ACTIVE,
        )
        TenantUser.objects.create(
            tenant=tenant_two,
            user_id=self.user.id,
            status=TenantUserStatus.ACTIVE,
        )
        self.user.last_tenant_id = tenant_two.id
        self.user.save(update_fields=["last_tenant_id", "updated_at"])

        response = self.client.post(
            "/api/auth/login",
            {"login_name": self.user.login_name, "password": self.password_plain},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertIn("tenant", data)
        self.assertEqual(data["tenant"]["id"], tenant_two.id)

    def test_login_rate_limited(self):
        """触发限流"""
        with patch("apps.accounts.services.auth.is_rate_limited", return_value=True):
            response = self.client.post(
                "/api/auth/login",
                {"login_name": self.user.login_name, "password": self.password_plain},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["code"], "AUTH_TOO_MANY_ATTEMPTS")


class RefreshAPITest(TestCase):
    """刷新接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = GlobalUser.objects.create(
            login_name="bob",
            display_name="Bob",
            email="bob@example.com",
            password_hash=make_password("Password123!"),
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=True,
        )

    def _create_session(self, *, status: str = AuthSessionStatus.ACTIVE, expires_at=None):
        refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)
        if expires_at is None:
            expires_at = timezone.now() + timedelta(days=1)
        session = AuthSession.objects.create(
            user=self.user,
            refresh_token_hash=refresh_hash,
            status=status,
            issued_at=timezone.now(),
            expires_at=expires_at,
            device_info={},
        )
        return session, refresh_token

    def test_refresh_success(self):
        """成功刷新：返回新 access_token，轮换 refresh cookie"""
        _, refresh_token = self._create_session()
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertIn("access_token", data)
        self.assertIn("expires_in", data)
        self.assertIn("user", data)

        cookie = response.cookies.get(auth_service.REFRESH_COOKIE_NAME)
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie.get("httponly"))

    def test_refresh_missing_cookie(self):
        """缺少 refresh cookie"""
        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_INVALID_TOKEN")

    def test_refresh_invalid_token(self):
        """refresh token 无效"""
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = "invalid-token"

        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_INVALID_TOKEN")

    def test_refresh_session_revoked(self):
        """会话已撤销"""
        _, refresh_token = self._create_session(status=AuthSessionStatus.REVOKED)
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_SESSION_REVOKED")

    def test_refresh_session_expired(self):
        """会话已过期"""
        expired_at = timezone.now() - timedelta(seconds=1)
        _, refresh_token = self._create_session(expires_at=expired_at)
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_SESSION_EXPIRED")

    def test_refresh_user_disabled(self):
        """用户被禁用"""
        _, refresh_token = self._create_session()
        self.user.status = GlobalUserStatus.DISABLED
        self.user.save(update_fields=["status", "updated_at"])
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/refresh")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "AUTH_USER_DISABLED")


class LogoutAPITest(TestCase):
    """登出接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.user = GlobalUser.objects.create(
            login_name="charlie",
            display_name="Charlie",
            email="charlie@example.com",
            password_hash=make_password("Password123!"),
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=False,
        )

    def _create_session(self, *, status_value: str = AuthSessionStatus.ACTIVE):
        refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)
        session = AuthSession.objects.create(
            user=self.user,
            refresh_token_hash=refresh_hash,
            status=status_value,
            issued_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=1),
            revoked_at=(timezone.now() if status_value == AuthSessionStatus.REVOKED else None),
            device_info={},
        )
        return session, refresh_token

    def test_logout_success_revokes_session_and_clears_cookie(self):
        """成功登出：撤销会话并清理 refresh cookie"""
        session, refresh_token = self._create_session()
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")

        session.refresh_from_db()
        self.assertEqual(session.status, AuthSessionStatus.REVOKED)
        self.assertIsNotNone(session.revoked_at)

        cookie = response.cookies.get(auth_service.REFRESH_COOKIE_NAME)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie.get("max-age"), 0)

    def test_logout_missing_cookie(self):
        """未登录：缺少 refresh cookie"""
        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_INVALID_TOKEN")

    def test_logout_session_not_found(self):
        """无 session：refresh token 不存在"""
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = "missing-session-token"

        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "AUTH_INVALID_TOKEN")

    def test_logout_session_revoked(self):
        """会话已撤销：返回 OK"""
        session, refresh_token = self._create_session(status_value=AuthSessionStatus.REVOKED)
        revoked_at = session.revoked_at
        self.client.cookies[auth_service.REFRESH_COOKIE_NAME] = refresh_token

        response = self.client.post("/api/auth/logout")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")

        session.refresh_from_db()
        self.assertEqual(session.status, AuthSessionStatus.REVOKED)
        self.assertEqual(session.revoked_at, revoked_at)
