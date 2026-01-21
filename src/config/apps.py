from django.apps import AppConfig


class ConfigConfig(AppConfig):
    """
    Config 应用的配置类
    
    在 Django 应用完全初始化后重新加载 DRF 配置，
    确保 api_settings 能正确读取 settings.REST_FRAMEWORK
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "config"

    def ready(self):
        """应用初始化完成后执行"""
        from config.settings.base import _reload_drf_settings
        _reload_drf_settings()

