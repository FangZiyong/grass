"""
JWT Access Token 签发与验签工具。

根据 tech.md §4.3.1：
- Access Token（JWT）：短期有效（例如 15 分钟），用于鉴权与携带 user_id/is_platform_admin 等声明。
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import jwt
from django.conf import settings
from rest_framework import status

from common.errors.codes import ErrorCode
from common.errors.exceptions import GrassAPIException


# JWT 配置
JWT_SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_TTL = 900  # 15 分钟（秒）
REFRESH_TOKEN_BYTES = getattr(settings, "AUTH_REFRESH_TOKEN_BYTES", 32)
REFRESH_TOKEN_SALT = getattr(settings, "AUTH_REFRESH_TOKEN_SALT", settings.SECRET_KEY)


class TokenPayload:
    """JWT payload 结构"""

    def __init__(self, user_id: int, is_platform_admin: bool = False):
        self.user_id = user_id
        self.is_platform_admin = is_platform_admin

    def to_dict(self) -> dict[str, Any]:
        """转换为字典用于 JWT 编码"""
        return {
            "user_id": self.user_id,
            "is_platform_admin": self.is_platform_admin,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TokenPayload":
        """从字典创建 TokenPayload"""
        return cls(
            user_id=payload.get("user_id"),
            is_platform_admin=payload.get("is_platform_admin", False),
        )


class TokenError(GrassAPIException):
    """Token 相关错误"""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = ErrorCode.UNAUTHENTICATED


def issue_access_token(user_id: int, is_platform_admin: bool = False) -> tuple[str, int]:
    """
    签发 access token。

    Args:
        user_id: 用户 ID
        is_platform_admin: 是否为平台管理员

    Returns:
        (token, expires_in): token 字符串和过期时间（秒）
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=JWT_ACCESS_TOKEN_TTL)

    payload = {
        "user_id": user_id,
        "is_platform_admin": is_platform_admin,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, JWT_ACCESS_TOKEN_TTL


def verify_access_token(token: str) -> TokenPayload:
    """
    验证 access token 并返回 payload。

    Args:
        token: JWT token 字符串

    Returns:
        TokenPayload: 解析后的 payload

    Raises:
        TokenError: token 无效、过期或签名错误
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": True, "verify_signature": True},
        )
    except jwt.ExpiredSignatureError:
        raise TokenError(
            detail="Access token has expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )
    except jwt.InvalidTokenError as e:
        raise TokenError(
            detail=f"Invalid access token: {str(e)}",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )

    # 校验 token 类型
    if payload.get("type") != "access":
        raise TokenError(
            detail="Invalid token type.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )

    # 校验必需字段
    user_id = payload.get("user_id")
    if not user_id:
        raise TokenError(
            detail="Token missing user_id.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHENTICATED,
        )

    return TokenPayload(
        user_id=user_id,
        is_platform_admin=payload.get("is_platform_admin", False),
    )


def extract_token_from_header(authorization_header: Optional[str]) -> Optional[str]:
    """
    从 Authorization header 中提取 token。

    Args:
        authorization_header: Authorization header 值，格式为 "Bearer <token>"

    Returns:
        token 字符串，如果格式不正确则返回 None
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def generate_refresh_token() -> str:
    """
    生成 refresh token。
    """
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(refresh_token: str) -> str:
    """
    对 refresh token 做不可逆哈希存储。
    """
    key = str(REFRESH_TOKEN_SALT).encode("utf-8")
    return hmac.new(key, refresh_token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_refresh_token_hash(refresh_token: str, token_hash: str) -> bool:
    """
    比较 refresh token 与 hash 是否匹配。
    """
    return hmac.compare_digest(hash_refresh_token(refresh_token), token_hash)

