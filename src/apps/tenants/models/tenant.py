"""
Tenant 模型：租户实体
"""
from django.db import models


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
        return f"Tenant(id={self.id}, code={self.code}, name={self.name}, status={self.status})"

