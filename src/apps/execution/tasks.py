"""
Celery 任务定义
"""
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Celery 未安装时，使用占位符
    CELERY_AVAILABLE = False
    
    def shared_task(*args, **kwargs):
        """占位符装饰器，当 Celery 不可用时"""
        def decorator(func):
            return func
        return decorator

from apps.execution.worker.base import execute_task_async


if CELERY_AVAILABLE:
    @shared_task(bind=True, max_retries=3)
    def execute_task(self, task_run_id: int):
        """
        Celery 任务：执行 TaskRunInstance
        
        Args:
            task_run_id: 任务运行实例ID
        """
        try:
            execute_task_async(task_run_id)
        except Exception as e:
            # Celery 重试机制
            raise self.retry(exc=e, countdown=60)
else:
    # Celery 不可用时的占位符函数
    def execute_task(task_run_id: int):
        """占位符函数，当 Celery 不可用时直接同步执行"""
        execute_task_async(task_run_id)

