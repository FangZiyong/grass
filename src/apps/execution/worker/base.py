"""
Worker 基类：统一处理重试、超时、异常映射、写回状态
"""
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from django.utils import timezone

from apps.execution.models.task_run import TaskRunInstance, TaskRunStatus

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Worker 基类
    
    业务 Worker 需要继承此类并实现 execute 方法。
    
    示例：
    ```python
    class DatasetRefreshWorker(BaseWorker):
        def execute(self, task_run: TaskRunInstance) -> Dict[str, Any]:
            # 业务逻辑
            dataset_id = task_run.task_id
            # ... 执行刷新
            return {"row_count": 1000}
    ```
    """
    
    def __init__(self, task_run: TaskRunInstance):
        self.task_run = task_run
    
    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        执行任务逻辑（由子类实现）
        
        Returns:
            输出数据字典（将写入 task_run.output_data）
            
        Raises:
            Exception: 任务执行失败时抛出异常
        """
        raise NotImplementedError("Subclass must implement execute()")
    
    def validate(self) -> bool:
        """
        任务执行前校验（可选，由子类覆盖）
        
        Returns:
            校验是否通过
        """
        return True
    
    def on_success(self, output_data: Dict[str, Any]):
        """
        任务成功回调（可选，由子类覆盖）
        """
        pass
    
    def on_failure(self, error: Exception):
        """
        任务失败回调（可选，由子类覆盖）
        """
        pass


def execute_task_sync(task_run_id: int):
    """
    同步执行任务（用于测试或直接调用）
    
    Args:
        task_run_id: 任务运行实例ID
    """
    try:
        task_run = TaskRunInstance.objects.select_for_update().get(id=task_run_id)
    except TaskRunInstance.DoesNotExist:
        logger.error(f"TaskRun {task_run_id} not found")
        return
    
    # 检查状态
    if task_run.status not in [TaskRunStatus.READY, TaskRunStatus.PENDING]:
        logger.warning(
            f"TaskRun {task_run_id} status is {task_run.status}, "
            f"cannot execute (expected READY or PENDING)"
        )
        return
    
    # 如果是 PENDING，先标记为 READY
    if task_run.status == TaskRunStatus.PENDING:
        task_run.mark_ready()
    
    # 获取处理器（延迟导入避免循环依赖）
    from apps.execution.registry.tasks import registry
    
    handler_class = registry.get_handler(task_run.task_type)
    if not handler_class:
        logger.error(f"Task type '{task_run.task_type}' not registered")
        task_run.mark_failed(
            error_code="TASK_HANDLER_NOT_FOUND",
            error_message=f"Task type '{task_run.task_type}' not registered in ExecutionRegistry",
        )
        return
    
    # 创建 worker 实例
    worker = handler_class(task_run)
    
    # 标记为运行中
    worker_id = f"sync_{task_run_id}"
    task_run.mark_running(worker_id=worker_id)
    
    try:
        # 校验
        if not worker.validate():
            raise ValueError("Task validation failed")
        
        # 执行
        output_data = worker.execute()
        
        # 标记成功
        task_run.mark_success(output_data=output_data)
        worker.on_success(output_data)
        
        logger.info(f"TaskRun {task_run_id} executed successfully")
        
    except Exception as e:
        # 处理异常
        error_code = getattr(e, "error_code", "INTERNAL_ERROR")
        error_message = str(e)
        
        # 如果错误信息过长，截断
        if len(error_message) > 2048:
            error_message = error_message[:2045] + "..."
        
        # 检查是否可以重试
        if task_run.can_retry():
            task_run.retry_count += 1
            task_run.status = TaskRunStatus.PENDING  # 重置为待执行，等待重试
            task_run.save(update_fields=["retry_count", "status", "updated_at"])
            logger.info(
                f"TaskRun {task_run_id} failed, will retry "
                f"(retry_count={task_run.retry_count}/{task_run.max_retries})"
            )
        else:
            # 标记失败
            task_run.mark_failed(
                error_code=error_code,
                error_message=error_message,
            )
            worker.on_failure(e)
            logger.error(
                f"TaskRun {task_run_id} failed: {error_code} - {error_message}",
                exc_info=True,
            )


def execute_task_async(task_run_id: int):
    """
    异步执行任务（Celery task 入口）
    
    Args:
        task_run_id: 任务运行实例ID
    """
    execute_task_sync(task_run_id)

