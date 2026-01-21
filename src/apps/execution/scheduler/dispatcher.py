"""
调度器：将 TaskRunInstance 投递到队列
"""
import logging
from typing import Optional

from django.conf import settings

from apps.execution.models.task_run import TaskRunInstance, TaskRunStatus

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """
    任务调度器
    
    负责将 READY/RUNNING 状态的任务派发到 Celery 队列或直接调用 worker。
    """
    
    @staticmethod
    def dispatch(task_run: TaskRunInstance, use_celery: bool = True) -> bool:
        """
        派发任务到执行队列
        
        Args:
            task_run: 任务运行实例
            use_celery: 是否使用 Celery（True）或直接调用（False，用于测试）
            
        Returns:
            是否派发成功
        """
        if task_run.status not in [TaskRunStatus.READY, TaskRunStatus.RUNNING]:
            logger.warning(
                f"TaskRun {task_run.id} status is {task_run.status}, "
                f"cannot dispatch (expected READY or RUNNING)"
            )
            return False
        
        if use_celery:
            try:
                from apps.execution.tasks import execute_task
                
                # 使用 Celery delay 异步执行
                execute_task.delay(task_run.id)
                logger.info(f"Dispatched TaskRun {task_run.id} to Celery queue")
                return True
            except (ImportError, AttributeError) as e:
                logger.warning(f"Celery not available ({e}), falling back to direct call")
                use_celery = False
        
        if not use_celery:
            # 直接调用（用于测试或开发环境）
            try:
                from apps.execution.worker.base import execute_task_sync
                
                execute_task_sync(task_run.id)
                logger.info(f"Executed TaskRun {task_run.id} synchronously")
                return True
            except Exception as e:
                logger.error(f"Failed to execute TaskRun {task_run.id} synchronously: {e}")
                return False
        
        return False
    
    @staticmethod
    def dispatch_ready_tasks(limit: int = 100) -> int:
        """
        扫描并派发所有 READY 状态的任务
        
        Args:
            limit: 每次扫描的最大任务数
            
        Returns:
            派发的任务数
        """
        ready_tasks = TaskRunInstance.objects.filter(
            status=TaskRunStatus.READY
        ).order_by("created_at")[:limit]
        
        dispatched = 0
        for task in ready_tasks:
            if TaskDispatcher.dispatch(task):
                dispatched += 1
        
        return dispatched
    
    @staticmethod
    def dispatch_running_tasks(limit: int = 100) -> int:
        """
        扫描并重新派发 RUNNING 状态但可能卡住的任务（超时检测）
        
        Args:
            limit: 每次扫描的最大任务数
            
        Returns:
            重新派发的任务数
        """
        from django.utils import timezone
        from datetime import timedelta
        
        # 查找运行时间超过超时时间的任务
        now = timezone.now()
        running_tasks = TaskRunInstance.objects.filter(
            status=TaskRunStatus.RUNNING,
            started_at__isnull=False,
        ).select_for_update()
        
        re_dispatched = 0
        for task in running_tasks[:limit]:
            # 检查是否超时
            if task.timeout_seconds and task.started_at:
                elapsed = (now - task.started_at).total_seconds()
                if elapsed > task.timeout_seconds:
                    logger.warning(
                        f"TaskRun {task.id} timeout detected "
                        f"(elapsed={elapsed}s, timeout={task.timeout_seconds}s)"
                    )
                    task.mark_timeout()
                    re_dispatched += 1
        
        return re_dispatched

