"""
认证上下文中间件/DRF Authentication Class。

根据 tech.md §4.3.1 和 §4.5.1：
- 验证 access token（JWT）
- 将 user 信息注入到 request.user
- 为后续权限判断提供 user_id、is_platform_admin 等字段
"""
from typing import Optional, Tuple

from rest_framework import authentication, exceptions
from rest_framework.request import Request

from apps.accounts.services.tokens import TokenError, extract_token_from_header, verify_access_token


class AuthContextUser:
    """
    认证上下文用户对象，用于替代 Django User。
    提供 user_id 和 is_platform_admin 等字段。
    """

    def __init__(self, user_id: int, is_platform_admin: bool = False):
        self.id = user_id
        self.user_id = user_id
        self.is_platform_admin = is_platform_admin
        self.is_authenticated = True
        self.is_active = True  # 由后续中间件/权限类校验用户状态

    def __str__(self):
        return f"AuthContextUser(id={self.id}, is_platform_admin={self.is_platform_admin})"


class JWTAuthentication(authentication.BaseAuthentication):
    """
    JWT 认证类，用于 DRF。

    从 Authorization header 中提取 Bearer token，验证后设置 request.user。
    """

    def authenticate(self, request: Request) -> Optional[Tuple[AuthContextUser, None]]:
        """
        认证请求。

        Returns:
            (user, None) 如果认证成功
            None 如果未提供 token（允许匿名访问）
        Raises:
            AuthenticationFailed 如果 token 无效
        """
        authorization_header = request.headers.get("Authorization") or request.META.get(
            "HTTP_AUTHORIZATION"
        )

        token = extract_token_from_header(authorization_header)
        if not token:
            # 未提供 token，返回 None 允许匿名访问（由权限类决定是否需要认证）
            return None

        try:
            payload = verify_access_token(token)
        except TokenError as e:
            # 将 TokenError 转换为 DRF 的 AuthenticationFailed
            raise exceptions.AuthenticationFailed(str(e.detail))

        # 创建认证用户对象
        user = AuthContextUser(
            user_id=payload.user_id,
            is_platform_admin=payload.is_platform_admin,
        )

        return (user, None)

    def authenticate_header(self, request: Request) -> str:
        """
        返回 WWW-Authenticate header 的值。
        """
        return "Bearer"

