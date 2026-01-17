"""
ExecutionRegistry：任务类型 -> handler 注册表

业务模块在 AppConfig.ready() 中注册任务处理器。
"""
from typing import TYPE_CHECKING, Callable, Dict, Type

if TYPE_CHECKING:
    from apps.execution.worker.base import BaseWorker


class ExecutionRegistry:
    """
    任务执行注册表
    
    用法：
    ```python
    # 在业务模块的 apps.py 中注册
    from apps.execution.registry import ExecutionRegistry
    from apps.reports.workers.dataset_refresh import DatasetRefreshWorker
    
    ExecutionRegistry.register("DATASET_REFRESH", DatasetRefreshWorker)
    ```
    """
    
    _handlers: Dict[str, Type] = {}
    
    @classmethod
    def register(cls, task_type: str, handler_class: Type):
        """
        注册任务处理器
        
        Args:
            task_type: 任务类型（如 "DATASET_REFRESH"）
            handler_class: Worker 类（继承自 BaseWorker）
        """
        if task_type in cls._handlers:
            raise ValueError(f"Task type '{task_type}' already registered")
        cls._handlers[task_type] = handler_class
    
    @classmethod
    def get_handler(cls, task_type: str) -> Type | None:
        """
        获取任务处理器
        
        Args:
            task_type: 任务类型
            
        Returns:
            Worker 类，如果未注册则返回 None
        """
        return cls._handlers.get(task_type)
    
    @classmethod
    def is_registered(cls, task_type: str) -> bool:
        """检查任务类型是否已注册"""
        return task_type in cls._handlers
    
    @classmethod
    def list_task_types(cls) -> list[str]:
        """列出所有已注册的任务类型"""
        return list(cls._handlers.keys())


# 全局注册表实例
registry = ExecutionRegistry()

