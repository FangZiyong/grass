"""
Tenant 模型：租户实体
"""
import re

from django.db import IntegrityError
from django.db import models
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr


class TenantStatus(models.TextChoices):
    """租户状态枚举"""
    ACTIVE = "ACTIVE", "活跃"
    SUSPENDED = "SUSPENDED", "已停用"


class TenantPlan(models.TextChoices):
    """租户套餐枚举"""
    BASIC = "BASIC", "基础版"
    PRO = "PRO", "专业版"
    ENTERPRISE = "ENTERPRISE", "企业版"


class Tenant(models.Model):
    """
    租户模型
    
    根据 tech.md §4.2.2：
    - code: 租户编码（全局唯一，不可修改）
    - name: 租户名称（允许编辑）
    - status: ACTIVE/SUSPENDED（SUSPENDED时前台403、调度停止）
    - plan: BASIC/PRO/ENTERPRISE
    """
    
    tenant_id = models.BigAutoField(primary_key=True, help_text="租户ID")
    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="租户编码（全局唯一，不可修改）",
    )
    name = models.CharField(
        max_length=128,
        help_text="租户名称（允许编辑）",
    )
    status = models.CharField(
        max_length=16,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        db_index=True,
        help_text="租户状态：ACTIVE=活跃，SUSPENDED=已停用",
    )
    plan = models.CharField(
        max_length=16,
        choices=TenantPlan.choices,
        default=TenantPlan.BASIC,
        db_index=True,
        help_text="租户套餐：BASIC/PRO/ENTERPRISE",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "tenant"
        indexes = [
            models.Index(fields=["status"], name="idx_tenant_status"),
            models.Index(fields=["plan"], name="idx_tenant_plan"),
            models.Index(fields=["name"], name="idx_tenant_name"),
        ]
    
    def __str__(self):
        return (
            f"Tenant(tenant_id={self.tenant_id}, code={self.code}, "
            f"name={self.name}, status={self.status})"
        )

    _AUTO_CODE_PREFIX = "TENANT_"
    _AUTO_CODE_START = 1000
    _AUTO_CODE_RE = re.compile(r"^TENANT_(\d+)$")

    @classmethod
    def _next_auto_code(cls) -> str:
        base = cls._AUTO_CODE_START - 1

        agg = (
            cls.objects.filter(code__startswith=cls._AUTO_CODE_PREFIX)
            .annotate(n=Cast(Substr("code", len(cls._AUTO_CODE_PREFIX) + 1), IntegerField()))
            .aggregate(max_n=Max("n"))
        )
        max_n = agg.get("max_n")
        max_n = int(max_n) if max_n is not None else base
        return f"{cls._AUTO_CODE_PREFIX}{max_n + 1}"

    def save(self, *args, **kwargs):
        """
        tenant_code / code 后端自动生成（全局递增）：TENANT_1000 起。

        并发下依赖唯一约束 (code) + 重试保证不冲突。
        """
        if not self.code:
            last_err: Exception | None = None
            for _ in range(6):
                self.code = self.__class__._next_auto_code()
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError as e:
                    last_err = e
                    continue
            raise IntegrityError("生成 tenant code 失败") from last_err
        return super().save(*args, **kwargs)

