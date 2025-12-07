"""
多租户 Manager 和 QuerySet
用于自动过滤租户数据
"""
from django.db import models
from django.utils import timezone


class TenantQuerySet(models.QuerySet):
    """
    租户过滤 QuerySet
    自动添加 tenant_id 过滤条件
    """
    def for_tenant(self, tenant_id):
        """显式指定租户ID进行过滤"""
        return self.filter(tenant_id=tenant_id)

    def get_queryset(self):
        """获取当前租户的查询集"""
        # 这里可以从 thread local 或上下文获取 tenant_id
        # 暂时返回原始查询集，具体实现需要在中间件中设置上下文
        return self


class TenantManager(models.Manager):
    """
    租户 Manager
    自动为所有查询添加租户过滤
    """
    def get_queryset(self):
        """
        获取查询集时自动添加租户过滤
        注意：tenant_id 需要从上下文（如 thread local）中获取
        """
        queryset = super().get_queryset()
        # TODO: 从 thread local 或上下文获取 tenant_id
        # 暂时返回原始查询集，具体实现需要在中间件中设置
        return queryset

    def for_tenant(self, tenant_id):
        """显式指定租户ID进行过滤"""
        return self.get_queryset().filter(tenant_id=tenant_id)

