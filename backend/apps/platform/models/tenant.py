"""
租户模型 (Tenant)
逻辑隔离单位（公司/组织/项目）
"""
from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError

from apps.common.models import BaseModel


class TenantStatus(models.TextChoices):
    """租户状态枚举"""
    ACTIVE = 'ACTIVE', '激活'
    SUSPENDED = 'SUSPENDED', '停用'


class TenantPlan(models.TextChoices):
    """租户套餐枚举"""
    BASIC = 'BASIC', '基础版'
    PRO = 'PRO', '专业版'
    ENTERPRISE = 'ENTERPRISE', '企业版'


class Tenant(BaseModel):
    """
    租户
    逻辑隔离单位（公司/组织/项目）
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='租户编码',
        help_text='1-50个字符，仅支持字母、数字、下划线，全局唯一',
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]+$',
                message='租户编码只能包含字母、数字和下划线'
            )
        ]
    )
    name = models.CharField(
        max_length=100,
        verbose_name='租户名称',
        help_text='1-100个字符'
    )
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        db_index=True,
        verbose_name='状态',
        help_text='SUSPENDED 表示整个租户被停用'
    )
    plan = models.CharField(
        max_length=20,
        choices=TenantPlan.choices,
        default=TenantPlan.BASIC,
        db_index=True,
        verbose_name='套餐',
        help_text='租户套餐类型'
    )

    class Meta:
        db_table = 'tenants'
        verbose_name = '租户'
        verbose_name_plural = '租户'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
            models.Index(fields=['plan']),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'

    def clean(self):
        """模型级别验证"""
        super().clean()
        if not self.code or len(self.code.strip()) == 0:
            raise ValidationError({'code': '租户编码不能为空'})
        if not self.name or len(self.name.strip()) == 0:
            raise ValidationError({'name': '租户名称不能为空'})
        if len(self.name) > 100:
            raise ValidationError({'name': '租户名称不能超过100个字符'})

    def save(self, *args, **kwargs):
        """保存前执行验证"""
        self.full_clean()
        super().save(*args, **kwargs)


