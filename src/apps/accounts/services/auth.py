"""
Auth 服务层：登录逻辑（创建会话 + 发放 refresh cookie）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models.sessions import AuthSession, AuthSessionStatus
from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.accounts.services.tokens import generate_refresh_token, hash_refresh_token, issue_access_token
from apps.tenants.selectors import list_user_tenants
from common.errors.exceptions import GrassAPIException

REFRESH_TOKEN_TTL_DAYS = getattr(settings, "AUTH_REFRESH_TOKEN_TTL_DAYS", 30)
REFRESH_COOKIE_NAME = getattr(settings, "AUTH_REFRESH_COOKIE_NAME", "refresh_token")
REFRESH_COOKIE_PATH = getattr(settings, "AUTH_REFRESH_COOKIE_PATH", "/")
REFRESH_COOKIE_SAMESITE = getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_SECURE = getattr(settings, "AUTH_REFRESH_COOKIE_SECURE", False)
REQUIRE_TLS = getattr(settings, "AUTH_REQUIRE_TLS", False)
REFRESH_ROTATE = getattr(settings, "AUTH_REFRESH_ROTATE", True)


@dataclass
class LoginResult:
    payload: dict[str, Any]
    refresh_token: str
    refresh_expires_at: timezone.datetime


@dataclass
class RefreshResult:
    payload: dict[str, Any]
    refresh_token: Optional[str]
    refresh_expires_at: Optional[timezone.datetime]


def login(login_name: str, password: str, request=None) -> LoginResult:
    """
    校验凭证并创建登录会话。
    """
    if REQUIRE_TLS and request is not None and not request.is_secure():
        raise GrassAPIException(
            detail="TLS is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SECURITY_TLS_REQUIRED",
        )

    user = GlobalUser.objects.filter(login_name=login_name).first()
    if user is None:
        raise GrassAPIException(
            detail="用户不存在或密码错误",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_CREDENTIALS",
        )

    if user.status != GlobalUserStatus.ACTIVE:
        raise GrassAPIException(
            detail="User is disabled.",
            status_code=status.HTTP_403_FORBIDDEN,
            code="AUTH_USER_DISABLED",
        )

    client_ip = _resolve_client_ip(request)
    if is_rate_limited(login_name, client_ip):
        raise GrassAPIException(
            detail="Too many attempts. Please try later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="AUTH_TOO_MANY_ATTEMPTS",
        )

    if not check_password(password, user.password_hash):
        record_failed_login(login_name, client_ip)
        raise GrassAPIException(
            detail="用户不存在或密码错误",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_CREDENTIALS",
        )

    access_token, expires_in = issue_access_token(
        user_id=user.id,
        is_platform_admin=user.is_platform_admin,
    )
    # refresh token 仅保存哈希，明文只下发给客户端：
    # - 数据库泄漏时降低风险
    # - 需要时可通过哈希校验匹配
    refresh_token = generate_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    now = timezone.now()
    refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    device_info = _build_device_info(request)

    try:
        with transaction.atomic():
            # 创建会话记录，便于：
            # - 主动撤销（logout/后台踢下线）
            # - 被动过期（超时/轮换）
            # - 审计设备信息
            AuthSession.objects.create(
                user=user,
                refresh_token_hash=refresh_hash,
                status=AuthSessionStatus.ACTIVE,
                issued_at=now,
                expires_at=refresh_expires_at,
                device_info=device_info,
            )
            GlobalUser.objects.filter(id=user.id).update(last_login_at=now)
    except Exception as exc:  # pragma: no cover - defensive
        raise GrassAPIException(
            detail=str(exc) or "Failed to create session.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="SESSION_CREATE_FAILED",
        )

    payload: dict[str, Any] = {
        "access_token": access_token,
        "expires_in": expires_in,
        "user": _build_user_payload(user),
    }
    tenant_payload = _resolve_login_tenant(user)
    if tenant_payload is not None:
        payload["tenant"] = tenant_payload

    return LoginResult(
        payload=payload,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


def set_refresh_cookie(response, refresh_token: str, expires_at: timezone.datetime) -> None:
    """
    写入 refresh token 的 HttpOnly Cookie。
    """
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max(int((expires_at - timezone.now()).total_seconds()), 0),
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response) -> None:
    """
    清理 refresh token 的 Cookie。
    """
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        "",
        max_age=0,
        expires=0,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
    )


def logout(request=None) -> None:
    """
    撤销当前 refresh 会话。
    """
    refresh_token = None
    if request is not None and hasattr(request, "COOKIES"):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise GrassAPIException(
            detail="Refresh token is missing.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_TOKEN",
        )

    refresh_hash = hash_refresh_token(refresh_token)
    session = AuthSession.objects.filter(refresh_token_hash=refresh_hash).first()
    if session is None:
        raise GrassAPIException(
            detail="Invalid refresh token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_TOKEN",
        )

    if session.status == AuthSessionStatus.ACTIVE:
        now = timezone.now()
        session.status = AuthSessionStatus.REVOKED
        session.revoked_at = now
        session.save(update_fields=["status", "revoked_at", "updated_at"])
def refresh(request=None) -> RefreshResult:
    """
    使用 refresh cookie 换取新的 access token。
    """
    refresh_token = None
    if request is not None and hasattr(request, "COOKIES"):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise GrassAPIException(
            detail="Refresh token is missing.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_TOKEN",
        )

    refresh_hash = hash_refresh_token(refresh_token)
    # 按哈希定位会话，避免存储明文 token：
    # - refresh cookie 泄漏可被单点撤销
    session = (
        AuthSession.objects.select_related("user")
        .filter(refresh_token_hash=refresh_hash)
        .first()
    )
    if session is None:
        raise GrassAPIException(
            detail="Invalid refresh token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_INVALID_TOKEN",
        )

    if session.status == AuthSessionStatus.REVOKED:
        raise GrassAPIException(
            detail="Refresh session is revoked.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_SESSION_REVOKED",
        )
    if session.status == AuthSessionStatus.EXPIRED:
        raise GrassAPIException(
            detail="Refresh session has expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_SESSION_EXPIRED",
        )

    now = timezone.now()
    if session.expires_at <= now:
        # 过期后持久化状态，便于后续审计与防重复使用
        session.status = AuthSessionStatus.EXPIRED
        session.save(update_fields=["status", "updated_at"])
        raise GrassAPIException(
            detail="Refresh session has expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_SESSION_EXPIRED",
        )

    user = session.user
    if user.status != GlobalUserStatus.ACTIVE:
        raise GrassAPIException(
            detail="User is disabled.",
            status_code=status.HTTP_403_FORBIDDEN,
            code="AUTH_USER_DISABLED",
        )

    access_token, expires_in = issue_access_token(
        user_id=user.id,
        is_platform_admin=user.is_platform_admin,
    )

    new_refresh_token: Optional[str] = None
    new_refresh_expires_at: Optional[timezone.datetime] = None
    if REFRESH_ROTATE:
        # 轮换 refresh：
        # - 换新 token 哈希
        # - 延长过期时间
        new_refresh_token = generate_refresh_token()
        session.refresh_token_hash = hash_refresh_token(new_refresh_token)
        session.issued_at = now
        new_refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
        session.expires_at = new_refresh_expires_at
        session.save(update_fields=["refresh_token_hash", "issued_at", "expires_at", "updated_at"])

    payload = {
        "access_token": access_token,
        "expires_in": expires_in,
        "user": _build_user_payload(user),
    }
    return RefreshResult(
        payload=payload,
        refresh_token=new_refresh_token,
        refresh_expires_at=new_refresh_expires_at,
    )


def is_rate_limited(login_name: str, client_ip: str) -> bool:
    """
    登录限流判断（占位实现，后续可接入 Redis 或其他限流器）。
    """
    return False


def record_failed_login(login_name: str, client_ip: str) -> None:
    """
    记录失败登录（占位实现，后续可接入 Redis 或其他限流器）。
    """
    return None


def _build_user_payload(user: GlobalUser) -> dict[str, Any]:
    payload = {
        "id": user.id,
        "login_name": user.login_name,
        "display_name": user.display_name,
        "email": user.email,
        "is_platform_admin": user.is_platform_admin,
    }
    if user.last_tenant_id:
        payload["last_tenant_id"] = user.last_tenant_id
    return payload


def _resolve_login_tenant(user: GlobalUser) -> Optional[dict[str, Any]]:
    tenants = list(list_user_tenants(user.id, status="ACTIVE"))
    if not tenants:
        return None
    if len(tenants) == 1:
        return _build_tenant_payload(tenants[0])
    if user.last_tenant_id:
        for tenant in tenants:
            if tenant.id == user.last_tenant_id:
                return _build_tenant_payload(tenant)
    return None


def _build_tenant_payload(tenant) -> dict[str, Any]:
    return {
        "id": tenant.id,
        "code": tenant.code,
        "name": tenant.name,
        "plan": tenant.plan,
    }


def _build_device_info(request) -> dict[str, str]:
    if request is None:
        return {}
    user_agent = (request.headers.get("User-Agent") if hasattr(request, "headers") else None) or ""
    device_id = (request.headers.get("X-Device-Id") if hasattr(request, "headers") else None) or ""
    return {
        "user_agent": user_agent[:512],
        "ip": _resolve_client_ip(request)[:64],
        "device_id": device_id[:64],
    }


def _resolve_client_ip(request) -> str:
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
