"""
AuthSession 模型：登录会话
"""
from django.db import models
from django.utils import timezone

from apps.accounts.models.users import GlobalUser


class AuthSessionStatus(models.TextChoices):
    """会话状态枚举"""

    ACTIVE = "ACTIVE", "活跃"
    REVOKED = "REVOKED", "已撤销"
    EXPIRED = "EXPIRED", "已过期"


class AuthSession(models.Model):
    """
    登录会话模型

    根据 tech.md §4.2.4：
    - user_id: 平台用户
    - refresh_token_hash: refresh token 哈希（唯一）
    - status: ACTIVE/REVOKED/EXPIRED
    - issued_at: 签发时间
    - expires_at: 过期时间
    - revoked_at: 撤销时间（可为空）
    - device_info: 设备信息（ua/ip/device_id）
    """

    auth_session_id = models.BigAutoField(primary_key=True, help_text="登录会话ID")
    user = models.ForeignKey(
        GlobalUser,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
        db_column="user_id",
        help_text="关联的平台用户",
    )
    refresh_token_hash = models.CharField(
        max_length=255,
        unique=True,
        help_text="refresh token 哈希存储（唯一）",
    )
    status = models.CharField(
        max_length=16,
        choices=AuthSessionStatus.choices,
        default=AuthSessionStatus.ACTIVE,
        help_text="会话状态：ACTIVE=活跃，REVOKED=已撤销，EXPIRED=已过期",
    )
    issued_at = models.DateTimeField(
        default=timezone.now,
        help_text="签发时间",
    )
    expires_at = models.DateTimeField(
        help_text="过期时间",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="撤销时间",
    )
    device_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="设备信息（ua/ip/device_id）",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_session"
        indexes = [
            models.Index(fields=["user", "status"], name="idx_auth_session_user"),
            models.Index(fields=["expires_at"], name="idx_auth_session_expires"),
        ]

    def __str__(self) -> str:
        return (
            "AuthSession("
            f"auth_session_id={self.auth_session_id}, user_id={self.user_id}, status={self.status}"
            ")"
        )
