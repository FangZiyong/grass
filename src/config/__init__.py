# 确保 Celery app 在 Django 启动时被导入（可选，如果 celery 未安装则跳过）
try:
    from config.celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:
    # Celery 未安装时，不导出 celery_app
    celery_app = None
    __all__ = ()

