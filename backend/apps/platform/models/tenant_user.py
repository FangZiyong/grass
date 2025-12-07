"""
租户用户模型 (TenantUser)
GlobalUser 与 Tenant 的关联关系，是权限控制的"人"的主体
"""
from django.db import models
from django.core.exceptions import ValidationError

from apps.common.models import TenantBaseModel, TenantManager


class TenantUserStatus(models.TextChoices):
    """租户用户状态枚举"""
    ACTIVE = 'ACTIVE', '激活'
    DISABLED = 'DISABLED', '禁用'


class TenantUser(TenantBaseModel):
    """
    租户用户
    GlobalUser 与 Tenant 的关联关系，是权限控制的"人"的主体
    """
    user = models.ForeignKey(
        'platform.GlobalUser',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='tenant_users',
        verbose_name='平台用户'
    )
    status = models.CharField(
        max_length=20,
        choices=TenantUserStatus.choices,
        default=TenantUserStatus.ACTIVE,
        db_index=True,
        verbose_name='状态',
        help_text='仅 ACTIVE 可登录该租户工作区'
    )
    is_owner = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='是否Owner',
        help_text='同一租户可有多个 Owner，但必须≥1'
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最近登录时间'
    )

    # 使用 TenantManager 自动过滤租户
    objects = TenantManager()

    class Meta:
        db_table = 'tenant_users'
        verbose_name = '租户用户'
        verbose_name_plural = '租户用户'
        ordering = ['-created_at']
        # (tenant_id, user_id) 必须唯一
        unique_together = [['tenant', 'user']]
        indexes = [
            models.Index(fields=['tenant', 'user']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'is_owner']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.user.display_name} @ {self.tenant.name}'

    def clean(self):
        """模型级别验证"""
        super().clean()
        # 检查租户状态：当租户 status 为 SUSPENDED 时，该租户下所有 TenantUser 不能访问工作区
        # 这个检查在业务逻辑层处理，模型层不做强制约束

    def save(self, *args, **kwargs):
        """保存前执行验证"""
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def validate_owner_constraint(cls, tenant_id):
        """
        验证租户至少有一个 Owner
        在删除或修改 TenantUser 的 is_owner 字段时调用
        """
        active_owners = cls.objects.filter(
            tenant_id=tenant_id,
            is_owner=True,
            status=TenantUserStatus.ACTIVE
        ).count()
        if active_owners < 1:
            raise ValidationError('租户必须至少有一个激活的 Owner')

