"""
平台用户模型 (GlobalUser)
平台级账号，一个 GlobalUser 可以加入多个租户
"""
import re
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.core.exceptions import ValidationError

from apps.common.models import BaseModel


class GlobalUserStatus(models.TextChoices):
    """平台用户状态枚举"""
    ACTIVE = 'ACTIVE', '激活'
    DISABLED = 'DISABLED', '禁用'


class GlobalUser(BaseModel):
    """
    平台用户
    一个 GlobalUser 可以加入多个租户
    """
    login_name = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='登录名',
        help_text='1-50个字符，仅支持字母、数字、下划线',
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]+$',
                message='登录名只能包含字母、数字和下划线'
            )
        ]
    )
    display_name = models.CharField(
        max_length=50,
        verbose_name='显示名称',
        help_text='1-50个字符'
    )
    email = models.EmailField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='邮箱',
        validators=[EmailValidator()]
    )
    status = models.CharField(
        max_length=20,
        choices=GlobalUserStatus.choices,
        default=GlobalUserStatus.ACTIVE,
        db_index=True,
        verbose_name='状态'
    )
    password = models.CharField(
        max_length=128,
        verbose_name='密码哈希',
        help_text='使用Django默认的PBKDF2算法存储'
    )

    class Meta:
        db_table = 'global_users'
        verbose_name = '平台用户'
        verbose_name_plural = '平台用户'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['login_name']),
            models.Index(fields=['email']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.display_name} ({self.login_name})'

    def clean(self):
        """模型级别验证"""
        super().clean()
        if not self.login_name or len(self.login_name.strip()) == 0:
            raise ValidationError({'login_name': '登录名不能为空'})
        if not self.display_name or len(self.display_name.strip()) == 0:
            raise ValidationError({'display_name': '显示名称不能为空'})
        if len(self.display_name) > 50:
            raise ValidationError({'display_name': '显示名称不能超过50个字符'})

    def save(self, *args, **kwargs):
        """保存前执行验证"""
        self.full_clean()
        super().save(*args, **kwargs)

