"""
T0.4 认证上下文完整测试。

测试覆盖（至少 5 个分支）：
1. 无 token（允许匿名访问）
2. token 过期
3. 签名错误/无效 token
4. 正常认证（普通用户）
5. 正常认证（平台管理员）
"""
import time
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.test import override_settings
from django.urls import path
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.test import APIClient, APISimpleTestCase
from rest_framework.views import APIView

from apps.accounts.api.permissions import IsAuthenticated, IsPlatformAdmin
from apps.accounts.services.tokens import (
    TokenError,
    extract_token_from_header,
    issue_access_token,
    verify_access_token,
)
from common.http.response import envelope_response
from common.middleware.auth_context import AuthContextUser, JWTAuthentication


# ==================== 测试视图 ====================
class PublicView(APIView):
    """公开视图，不需要认证"""

    def get(self, request):
        data = {
            "message": "public",
            "user": (
                str(request.user)
                if hasattr(request, "user")
                and hasattr(request.user, "is_authenticated")
                and request.user.is_authenticated
                else "anonymous"
            ),
        }
        return envelope_response(data, request=request)


class ProtectedView(APIView):
    """受保护视图，需要认证"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "message": "protected",
            "user_id": request.user.user_id,
            "is_platform_admin": request.user.is_platform_admin,
        }
        return envelope_response(data, request=request)


class AdminView(APIView):
    """管理员视图，需要平台管理员权限"""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        data = {
            "message": "admin",
            "user_id": request.user.user_id,
            "is_platform_admin": request.user.is_platform_admin,
        }
        return envelope_response(data, request=request)


urlpatterns = [
    path("api/auth/public", PublicView.as_view()),
    path("api/auth/protected", ProtectedView.as_view()),
    path("api/auth/admin", AdminView.as_view()),
]


# ==================== Token 工具函数测试 ====================
class TokenUtilsTests(APISimpleTestCase):
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
        self.assertEqual(expires_in, 86400)  # 24 小时

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
            "exp": int((expired_time - timedelta(seconds=10)).timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expired", str(cm.exception.detail).lower())

    def test_verify_access_token_invalid_signature(self):
        """测试验证签名错误的 token"""
        # 使用错误的密钥签名
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 86400,
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
            "exp": int(time.time()) + 86400,
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
            "exp": int(time.time()) + 86400,
            "type": "refresh",  # 错误类型
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(TokenError) as cm:
            verify_access_token(token)
        self.assertEqual(cm.exception.status_code, status.HTTP_401_UNAUTHORIZED)


# ==================== JWT 认证类测试 ====================
class JWTAuthenticationTests(APISimpleTestCase):
    """JWT 认证类测试"""

    def setUp(self):
        from rest_framework.test import APIRequestFactory

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
            "exp": int((expired_time - timedelta(seconds=10)).timestamp()),
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
            "exp": int(time.time()) + 86400,
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


# ==================== AuthContextUser 测试 ====================
class AuthContextUserTests(APISimpleTestCase):
    """AuthContextUser 测试"""

    def test_auth_context_user_creation(self):
        """测试创建 AuthContextUser"""
        user = AuthContextUser(user_id=1, is_platform_admin=False)
        self.assertEqual(user.user_id, 1)
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


# ==================== 端到端 API 测试 ====================
@override_settings(ROOT_URLCONF=__name__)
class AuthContextAPITests(APISimpleTestCase):
    """认证上下文端到端 API 测试"""

    client_class = APIClient

    def test_public_view_no_token(self):
        """测试公开视图，无 token（允许匿名访问）"""
        response = self.client.get("/api/auth/public")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["data"]["message"], "public")
        # 无 token 时应该是匿名用户
        self.assertIn("anonymous", body["data"]["user"])

    def test_protected_view_no_token(self):
        """测试受保护视图，无 token（应返回 401）"""
        response = self.client.get("/api/auth/protected")
        body = response.json()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        self.assertIn("request_id", body)

    def test_protected_view_valid_token(self):
        """测试受保护视图，有效 token（正常用户）"""
        token, _ = issue_access_token(user_id=100, is_platform_admin=False)
        response = self.client.get("/api/auth/protected", HTTP_AUTHORIZATION=f"Bearer {token}")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["data"]["message"], "protected")
        self.assertEqual(body["data"]["user_id"], 100)
        self.assertFalse(body["data"]["is_platform_admin"])

    def test_protected_view_expired_token(self):
        """测试受保护视图，过期 token（应返回 401）"""
        # 创建过期 token
        now = datetime.utcnow()
        expired_time = now - timedelta(seconds=1000)
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(expired_time.timestamp()),
            "exp": int((expired_time - timedelta(seconds=10)).timestamp()),
            "type": "access",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        response = self.client.get("/api/auth/protected", HTTP_AUTHORIZATION=f"Bearer {token}")
        body = response.json()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        self.assertIn("expired", body["message"].lower())

    def test_protected_view_invalid_signature(self):
        """测试受保护视图，签名错误的 token（应返回 401）"""
        payload = {
            "user_id": 1,
            "is_platform_admin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 86400,
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

        response = self.client.get("/api/auth/protected", HTTP_AUTHORIZATION=f"Bearer {token}")
        body = response.json()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")

    def test_admin_view_regular_user(self):
        """测试管理员视图，普通用户（应返回 403）"""
        token, _ = issue_access_token(user_id=100, is_platform_admin=False)
        response = self.client.get("/api/auth/admin", HTTP_AUTHORIZATION=f"Bearer {token}")
        body = response.json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["code"], "PERMISSION_DENIED")

    def test_admin_view_platform_admin(self):
        """测试管理员视图，平台管理员（应返回 200）"""
        token, _ = issue_access_token(user_id=200, is_platform_admin=True)
        response = self.client.get("/api/auth/admin", HTTP_AUTHORIZATION=f"Bearer {token}")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["data"]["message"], "admin")
        self.assertEqual(body["data"]["user_id"], 200)
        self.assertTrue(body["data"]["is_platform_admin"])

    def test_protected_view_malformed_header(self):
        """测试受保护视图，格式错误的 header（应返回 401）"""
        # 缺少 Bearer 前缀
        response = self.client.get("/api/auth/protected", HTTP_AUTHORIZATION="invalid_token")
        body = response.json()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")

    def test_response_includes_request_id(self):
        """测试响应包含 request_id"""
        token, _ = issue_access_token(user_id=100, is_platform_admin=False)
        custom_request_id = "req_test_auth_123"
        response = self.client.get(
            "/api/auth/protected",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_REQUEST_ID=custom_request_id,
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["request_id"], custom_request_id)
        self.assertEqual(response["X-Request-Id"], custom_request_id)
