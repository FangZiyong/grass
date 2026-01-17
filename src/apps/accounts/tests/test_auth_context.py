"""
T0.4 认证上下文测试。

测试覆盖：
1. 无 token（允许匿名访问）
2. token 过期
3. 签名错误/无效 token
4. 正常认证（普通用户）
5. 正常认证（平台管理员）
"""
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.accounts.services.tokens import (
    TokenError,
    extract_token_from_header,
    issue_access_token,
    verify_access_token,
)
from common.middleware.auth_context import AuthContextUser, JWTAuthentication


class TokenUtilsTests(TestCase):
    """Token 工具函数测试"""

    def test_extract_token_from_header_valid(self):
        """测试从有效的 Authorization header 中提取 token"""
        header = "Bearer test_token_123"
        token = extract_token_from_header(header)
        self.assertEqual(token, "test_token_123")

    def test_extract_token_from_header_invalid_format(self):
        """测试无效格式的 header"""
        # 缺少 Bearer 前缀
        token = extract_token_from_header("test_token_123")
        self.assertIsNone(token)

        # 多个部分
        token = extract_token_from_header("Bearer token1 token2")
        self.assertIsNone(token)

        # 空字符串
        token = extract_token_from_header("")
        self.assertIsNone(token)

        # None
        token = extract_token_from_header(None)
        self.assertIsNone(token)

    def test_issue_access_token(self):
        """测试签发 access token"""
        token, expires_in = issue_access_token(user_id=1, is_platform_admin=False)
        self.assertIsInstance(token, str)
        self.assertEqual(expires_in, 900)  # 15 分钟

        # 验证 token 可以解析
        payload = verify_access_token(token)
        self.assertEqual(payload.user_id, 1)
        self.assertFalse(payload.is_platform_admin)

    def test_issue_access_token_platform_admin(self):
        """测试签发平台管理员的 access token"""
        token, _ = issue_access_token(user_id=2, is_platform_admin=True)
        payload = verify_access_token(token)
        self.assertEqual(payload.user_id, 2)
        self.assertTrue(payload.is_platform_admin)

    def test_verify_access_token_valid(self):
        """测试验证有效的 token"""
        token, _ = issue_access_token(user_id=1, is_platform_admin=False)
        payload = verify_access_token(token)
        self.assertEqual(payload.user_id, 1)
        self.assertFalse(payload.is_platform_admin)

    def test_verify_access_token_expired(self):
        """测试验证过期的 token"""
        # 创建一个已过期的 token
        now = datetime.utcnow()
        expired_time = now - timedelta(seconds=1000)  # 过期时间
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(expired_time.timestamp()),
            "exp": int((expired_time + timedelta(seconds=900)).timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_access_token_invalid_signature(self):
        """测试验证签名错误的 token"""
        # 使用错误的密钥签名
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_access_token_missing_user_id(self):
        """测试缺少 user_id 的 token"""
        payload = {
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
            "type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("user_id", str(cm.exception.detail))

    def test_verify_access_token_wrong_type(self):
        """测试错误类型的 token"""
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
            "type": "refresh",  # 错误类型
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTAuthenticationTests(TestCase):
    """JWT 认证类测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth = JWTAuthentication()

    def test_authenticate_no_token(self):
        """测试无 token 的情况（允许匿名访问）"""
        request = self.factory.get("/api/test")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_authenticate_valid_token(self):
        """测试有效的 token"""
        token, _ = issue_access_token(user_id=1, is_platform_admin=False)
        request = self.factory.get("/api/test", HTTP_AUTHORIZATION=f"Bearer {token}")

        user, auth = self.auth.authenticate(request)
        self.assertIsInstance(user, AuthContextUser)
        self.assertEqual(user.user_id, 1)
        self.assertFalse(user.is_platform_admin)
        self.assertIsNone(auth)

    def test_authenticate_platform_admin_token(self):
        """测试平台管理员的 token"""
        token, _ = issue_access_token(user_id=2, is_platform_admin=True)
        request = self.factory.get("/api/test", HTTP_AUTHORIZATION=f"Bearer {token}")

        user, auth = self.auth.authenticate(request)
        self.assertIsInstance(user, AuthContextUser)
        self.assertEqual(user.user_id, 2)
        self.assertTrue(user.is_platform_admin)

    def test_authenticate_expired_token(self):
        """测试过期的 token"""
        # 创建过期 token
        now = datetime.utcnow()
        expired_time = now - timedelta(seconds=1000)
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(expired_time.timestamp()),
            "exp": int((expired_time + timedelta(seconds=900)).timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        request = self.factory.get("/api/test", HTTP_AUTHORIZATION=f"Bearer {token}")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_invalid_signature(self):
        """测试签名错误的 token"""
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

        request = self.factory.get("/api/test", HTTP_AUTHORIZATION=f"Bearer {token}")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_authenticate_malformed_header(self):
        """测试格式错误的 Authorization header"""
        # 缺少 Bearer 前缀
        request = self.factory.get("/api/test", HTTP_AUTHORIZATION="invalid_token")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

        # 空 header
        request = self.factory.get("/api/test", HTTP_AUTHORIZATION="")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_authenticate_header(self):
        """测试 authenticate_header 方法"""
        request = self.factory.get("/api/test")
        header = self.auth.authenticate_header(request)
        self.assertEqual(header, "Bearer")


class AuthContextUserTests(TestCase):
    """AuthContextUser 测试"""

    def test_auth_context_user_creation(self):
        """测试创建 AuthContextUser"""
        user = AuthContextUser(user_id=1, is_platform_admin=False)
        self.assertEqual(user.id, 1)
        self.assertEqual(user.user_id, 1)
        self.assertFalse(user.is_platform_admin)
        self.assertTrue(user.is_authenticated)
        self.assertTrue(user.is_active)

    def test_auth_context_user_platform_admin(self):
        """测试平台管理员用户"""
        user = AuthContextUser(user_id=2, is_platform_admin=True)
        self.assertTrue(user.is_platform_admin)

    def test_auth_context_user_string_representation(self):
        """测试字符串表示"""
        user = AuthContextUser(user_id=1, is_platform_admin=False)
        str_repr = str(user)
        self.assertIn("AuthContextUser", str_repr)
        self.assertIn("id=1", str_repr)
        self.assertIn("is_platform_admin=False", str_repr)

