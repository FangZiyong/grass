from django.apps import AppConfig


class ExecutionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.execution"
    verbose_name = "Execution"

    def ready(self):
        """App 初始化时注册任务处理器"""
        # 延迟导入，避免循环依赖
        # 业务模块可以在各自的 AppConfig.ready() 中注册任务处理器
        pass

