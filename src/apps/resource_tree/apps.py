"""
resource_tree 应用配置
"""
from django.apps import AppConfig


class ResourceTreeConfig(AppConfig):
    """资源树应用配置"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.resource_tree"
    verbose_name = "资源树"

    def ready(self):
        """应用启动时执行"""
        pass
