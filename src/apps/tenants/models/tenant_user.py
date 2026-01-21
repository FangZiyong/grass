"""
TenantUser 模型：租户成员关系
"""
from django.db import models

from apps.tenants.models.tenant import Tenant


class TenantUserStatus(models.TextChoices):
    """租户用户状态枚举"""
    ACTIVE = "ACTIVE", "活跃"
    DISABLED = "DISABLED", "已禁用"


class TenantUser(models.Model):
    """
    租户成员模型
    
    根据 tech.md §4.2.3：
    - tenant_id: 租户ID（FK → tenant.id）
    - user_id: 平台用户ID（FK → global_user.id，这里用IntegerField，后续T1.1会创建GlobalUser）
    - status: ACTIVE/DISABLED（仅影响该租户内访问）
    - is_owner: 是否该租户Owner（至少存在1个）
    - last_login: 最近一次进入该租户时间
    """
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="tenant_users",
        db_column="tenant_id",
        help_text="租户",
    )
    user_id = models.BigIntegerField(
        db_index=True,
        help_text="平台用户ID（FK → global_user.id）",
    )
    status = models.CharField(
        max_length=16,
        choices=TenantUserStatus.choices,
        default=TenantUserStatus.ACTIVE,
        help_text="租户用户状态：ACTIVE=活跃，DISABLED=已禁用",
    )
    is_owner = models.BooleanField(
        default=False,
        help_text="是否该租户Owner（至少存在1个）",
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="最近一次进入该租户时间",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "tenant_user"
        unique_together = [["tenant", "user_id"]]
        indexes = [
            models.Index(fields=["tenant", "user_id"], name="uk_tenant_user"),
            models.Index(fields=["tenant"], name="idx_tenant_user_tenant"),
            models.Index(fields=["user_id"], name="idx_tenant_user_user"),
            models.Index(fields=["tenant", "status"], name="idx_tenant_user_status"),
        ]
    
    def __str__(self):
        return f"TenantUser(id={self.id}, tenant_id={self.tenant_id}, user_id={self.user_id}, status={self.status})"

