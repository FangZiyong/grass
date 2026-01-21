"""
scheduler_tick 管理命令：扫描 READY/RUNNING 的任务并派发

用法：
    python manage.py scheduler_tick
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.execution.scheduler.dispatcher import TaskDispatcher


class Command(BaseCommand):
    help = "扫描 READY/RUNNING 的任务并派发到执行队列"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="每次扫描的最大任务数（默认：100）",
        )
        parser.add_argument(
            "--check-timeout",
            action="store_true",
            help="检查并处理超时任务",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        check_timeout = options["check_timeout"]
        
        self.stdout.write(
            self.style.SUCCESS(
                f"[{timezone.now()}] Starting scheduler tick (limit={limit})"
            )
        )
        
        # 派发 READY 任务
        ready_dispatched = TaskDispatcher.dispatch_ready_tasks(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(f"Dispatched {ready_dispatched} READY tasks")
        )
        
        # 检查超时任务（可选）
        if check_timeout:
            timeout_handled = TaskDispatcher.dispatch_running_tasks(limit=limit)
            self.stdout.write(
                self.style.SUCCESS(f"Handled {timeout_handled} timeout tasks")
            )
        
        self.stdout.write(
            self.style.SUCCESS(f"[{timezone.now()}] Scheduler tick completed")
        )

