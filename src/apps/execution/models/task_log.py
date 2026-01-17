"""
TaskRunLog 模型：任务运行日志（可选）
用于记录 worker 侧关键日志片段，避免跑满 audit_logs
"""
from django.db import models


class TaskRunLog(models.Model):
    """
    任务运行日志
    
    可选模型：若各业务 run 表已足够可不建。
    用于记录 worker 侧关键日志片段，避免跑满 audit_logs。
    """
    
    task_run = models.ForeignKey(
        "execution.TaskRunInstance",
        on_delete=models.CASCADE,
        related_name="logs",
        db_index=True,
        help_text="关联的任务运行实例",
    )
    level = models.CharField(
        max_length=16,
        choices=[
            ("DEBUG", "DEBUG"),
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
        ],
        default="INFO",
        help_text="日志级别",
    )
    message = models.TextField(
        help_text="日志消息",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="日志时间",
    )
    
    class Meta:
        db_table = "task_run_log"
        indexes = [
            models.Index(fields=["task_run", "created_at"], name="idx_task_run_created"),
        ]
        ordering = ["created_at"]
    
    def __str__(self):
        return f"TaskRunLog(id={self.id}, task_run={self.task_run_id}, level={self.level})"

