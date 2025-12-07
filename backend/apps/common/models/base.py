"""
基础模型类
提供通用字段和基础功能
"""
import uuid
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    基础模型类
    提供 id, created_at, updated_at 字段
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class TenantBaseModel(BaseModel):
    """
    租户基础模型类
    继承 BaseModel，并添加 tenant_id 外键
    注意：此模型不使用 TenantManager，因为某些模型（如 Tenant 本身）不需要租户过滤
    """
    tenant = models.ForeignKey(
        'platform.Tenant',
        on_delete=models.CASCADE,
        db_index=True,
        related_name='%(class)s_set'
    )

    class Meta:
        abstract = True

