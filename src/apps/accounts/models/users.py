"""
GlobalUser 模型：平台用户
"""
from django.db import models


class GlobalUserStatus(models.TextChoices):
    """平台用户状态枚举"""

    ACTIVE = "ACTIVE", "活跃"
    DISABLED = "DISABLED", "已禁用"


class GlobalUser(models.Model):
    """
    平台用户模型

    根据 tech.md §4.2.1：
    - login_name: 登录名（全局唯一，不可修改）
    - display_name: 显示名
    - email: 邮箱（全局唯一）
    - password_hash: 密码哈希
    - is_platform_admin: 平台管理员标识
    - status: ACTIVE/DISABLED（禁用后无法登录任何租户）
    - last_tenant_id: 最近进入的租户
    - last_login_at: 最近登录时间
    """

    login_name = models.CharField(
        max_length=64,
        unique=True,
        help_text="登录名（全局唯一，不可修改）",
    )
    display_name = models.CharField(
        max_length=64,
        help_text="显示名称",
    )
    email = models.EmailField(
        max_length=128,
        unique=True,
        help_text="邮箱（全局唯一）",
    )
    password_hash = models.CharField(
        max_length=255,
        help_text="密码哈希",
    )
    status = models.CharField(
        max_length=16,
        choices=GlobalUserStatus.choices,
        default=GlobalUserStatus.ACTIVE,
        db_index=True,
        help_text="用户状态：ACTIVE=活跃，DISABLED=已禁用",
    )
    is_platform_admin = models.BooleanField(
        default=False,
        db_index=True,
        help_text="是否平台管理员",
    )
    last_login_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="最近登录时间",
    )
    last_tenant_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="最近访问的租户ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "global_user"
        indexes = [
            models.Index(fields=["status"], name="idx_global_user_status"),
            models.Index(fields=["is_platform_admin"], name="idx_global_user_admin"),
        ]

    def __str__(self) -> str:
        return (
            "GlobalUser("
            f"id={self.id}, login_name={self.login_name}, "
            f"email={self.email}, status={self.status}"
            ")"
        )
