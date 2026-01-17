"""
权限类定义。

提供基础的认证权限检查。
"""
from rest_framework import permissions

from common.middleware.auth_context import AuthContextUser


class IsAuthenticated(permissions.BasePermission):
    """
    要求用户已认证（已登录）。

    检查 request.user 是否为 AuthContextUser 且已认证。
    """

    def has_permission(self, request, view):
        return (
            hasattr(request, "user")
            and isinstance(request.user, AuthContextUser)
            and request.user.is_authenticated
        )


class IsPlatformAdmin(permissions.BasePermission):
    """
    要求用户是平台管理员。

    检查 request.user.is_platform_admin 是否为 True。
    """

    def has_permission(self, request, view):
        if not hasattr(request, "user") or not isinstance(request.user, AuthContextUser):
            return False
        if not request.user.is_authenticated:
            return False
        return request.user.is_platform_admin

