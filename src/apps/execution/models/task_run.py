"""
TaskRunInstance 模型：通用任务运行实体
"""
from django.db import models
from django.utils import timezone


class TaskRunStatus(models.TextChoices):
    """任务运行状态枚举"""
    PENDING = "PENDING", "待执行"
    READY = "READY", "就绪（等待调度）"
    RUNNING = "RUNNING", "运行中"
    SUCCESS = "SUCCESS", "成功"
    FAILED = "FAILED", "失败"
    CANCELLED = "CANCELLED", "已取消"
    TIMEOUT = "TIMEOUT", "超时"


class TaskType(models.TextChoices):
    """任务类型枚举（由业务模块注册）"""
    # 示例类型，实际由业务模块注册
    DATASET_REFRESH = "DATASET_REFRESH", "数据集刷新"
    EXPORT = "EXPORT", "导出任务"
    FLOW_RUN = "FLOW_RUN", "流程运行"


class TaskRunInstance(models.Model):
    """
    通用任务运行实体
    
    根据 architecture.md execution 模块：
    - task_type: 任务类型（由 ExecutionRegistry 注册）
    - task_id: 业务任务ID（如 dataset_id/export_job_id/flow_run_id）
    - status: 状态机（PENDING/READY/RUNNING/SUCCESS/FAILED/CANCELLED/TIMEOUT）
    - tenant_id: 租户隔离
    - 支持重试、超时、幂等、并发抢占
    """
    
    task_run_id = models.BigAutoField(primary_key=True, help_text="任务运行ID")
    task_type = models.CharField(
        max_length=64,
        db_index=True,
        help_text="任务类型（由 ExecutionRegistry 注册）",
    )
    task_id = models.BigIntegerField(
        db_index=True,
        help_text="业务任务ID（如 dataset_id/export_job_id/flow_run_id）",
    )
    tenant_id = models.BigIntegerField(
        db_index=True,
        help_text="租户ID（多租户隔离）",
    )
    status = models.CharField(
        max_length=16,
        choices=TaskRunStatus.choices,
        default=TaskRunStatus.PENDING,
        db_index=True,
        help_text="运行状态",
    )
    
    # 执行上下文
    input_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="任务输入数据（JSON）",
    )
    output_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="任务输出数据（JSON）",
    )
    error_code = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="错误码（失败时）",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="错误信息（失败时，截断2KB）",
    )
    
    # 时间戳
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="开始执行时间",
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="完成时间",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 重试与超时
    retry_count = models.IntegerField(
        default=0,
        help_text="重试次数",
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="最大重试次数",
    )
    timeout_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="超时时间（秒），null表示无超时",
    )
    
    # 幂等与并发控制
    idempotency_key = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        help_text="幂等键（用于防重复执行）",
    )
    worker_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="执行worker标识",
    )
    request_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="请求ID（用于链路追踪）",
    )
    
    class Meta:
        db_table = "task_run_instance"
        indexes = [
            models.Index(fields=["task_type", "task_id"], name="idx_task_run_type_id"),
            models.Index(fields=["tenant_id", "status"], name="idx_task_run_tenant_status"),
            models.Index(fields=["status", "created_at"], name="idx_task_run_status_created"),
            models.Index(fields=["idempotency_key"], name="idx_task_run_idempotency_key"),
        ]
        # 同一任务类型+ID在同一租户下，同一时间只能有一个非终态任务
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "task_id", "tenant_id"],
                condition=models.Q(status__in=["PENDING", "READY", "RUNNING"]),
                name="uk_task_type_id_tenant_active",
            ),
        ]
    
    def __str__(self):
        return (
            f"TaskRunInstance(task_run_id={self.task_run_id}, type={self.task_type}, "
            f"task_id={self.task_id}, status={self.status})"
        )
    
    def mark_ready(self):
        """标记为就绪状态"""
        self.status = TaskRunStatus.READY
        self.save(update_fields=["status", "updated_at"])
    
    def mark_running(self, worker_id: str | None = None):
        """标记为运行中"""
        self.status = TaskRunStatus.RUNNING
        self.started_at = timezone.now()
        if worker_id:
            self.worker_id = worker_id
        self.save(update_fields=["status", "started_at", "worker_id", "updated_at"])
    
    def mark_success(self, output_data: dict | None = None):
        """标记为成功"""
        self.status = TaskRunStatus.SUCCESS
        self.finished_at = timezone.now()
        if output_data is not None:
            self.output_data = output_data
        self.save(update_fields=["status", "finished_at", "output_data", "updated_at"])
    
    def mark_failed(
        self,
        error_code: str,
        error_message: str,
        output_data: dict | None = None,
    ):
        """标记为失败"""
        self.status = TaskRunStatus.FAILED
        self.finished_at = timezone.now()
        self.error_code = error_code
        # 截断错误信息到2KB
        self.error_message = (error_message or "")[:2048]
        if output_data is not None:
            self.output_data = output_data
        self.save(
            update_fields=[
                "status",
                "finished_at",
                "error_code",
                "error_message",
                "output_data",
                "updated_at",
            ]
        )
    
    def mark_timeout(self):
        """标记为超时"""
        self.status = TaskRunStatus.TIMEOUT
        self.finished_at = timezone.now()
        self.error_code = "TASK_TIMEOUT"
        self.error_message = f"任务执行超时（timeout={self.timeout_seconds}s）"
        self.save(
            update_fields=["status", "finished_at", "error_code", "error_message", "updated_at"]
        )
    
    def can_retry(self) -> bool:
        """判断是否可以重试"""
        return self.retry_count < self.max_retries and self.status in [
            TaskRunStatus.FAILED,
            TaskRunStatus.TIMEOUT,
        ]
    
    def is_terminal(self) -> bool:
        """判断是否为终态"""
        return self.status in [
            TaskRunStatus.SUCCESS,
            TaskRunStatus.FAILED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.TIMEOUT,
        ]

