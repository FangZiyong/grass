"""
accounts 模型测试
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models.sessions import AuthSession, AuthSessionStatus
from apps.accounts.models.users import GlobalUser, GlobalUserStatus


class AccountsModelsTest(TestCase):
    """accounts 模型测试"""

    def test_create_global_user(self):
        """测试创建 GlobalUser"""
        user = GlobalUser.objects.create(
            login_name="alice",
            display_name="Alice",
            email="alice@example.com",
            password_hash="hashed-password",
        )

        self.assertIsNotNone(user.id)
        self.assertEqual(user.status, GlobalUserStatus.ACTIVE)
        self.assertFalse(user.is_platform_admin)
        self.assertIsNone(user.last_login_at)
        self.assertIsNone(user.last_tenant_id)

    def test_duplicate_email_conflict(self):
        """测试重复邮箱冲突"""
        GlobalUser.objects.create(
            login_name="user_a",
            display_name="UserA",
            email="dup@example.com",
            password_hash="hashed-a",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GlobalUser.objects.create(
                    login_name="user_b",
                    display_name="UserB",
                    email="dup@example.com",
                    password_hash="hashed-b",
                )

    def test_create_auth_session(self):
        """测试创建 AuthSession"""
        user = GlobalUser.objects.create(
            login_name="session_user",
            display_name="Session User",
            email="session@example.com",
            password_hash="hashed-password",
        )
        session = AuthSession.objects.create(
            user=user,
            refresh_token_hash="refresh-token-hash-1",
            expires_at=timezone.now() + timedelta(days=7),
        )

        self.assertIsNotNone(session.id)
        self.assertEqual(session.user_id, user.id)
        self.assertEqual(session.status, AuthSessionStatus.ACTIVE)
