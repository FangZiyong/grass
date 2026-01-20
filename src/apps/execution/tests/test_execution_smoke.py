"""
执行底座冒烟测试

测试覆盖：
- 状态迁移
- 重试
- handler 异常
- 超时
- 幂等
- 并发抢占
"""
import time
from unittest.mock import Mock, patch

from django.db import IntegrityError, connection
from django.test import TestCase
from django.utils import timezone

from apps.execution.models.task_run import TaskRunInstance, TaskRunStatus
from apps.execution.registry.tasks import ExecutionRegistry
from apps.execution.scheduler.dispatcher import TaskDispatcher
from apps.execution.worker.base import BaseWorker, execute_task_sync
from apps.tenants.models.tenant import Tenant


class MockWorker(BaseWorker):
    """测试用的 Mock Worker"""

    def __init__(self, task_run: TaskRunInstance, should_fail: bool = False, fail_message: str = ""):
        super().__init__(task_run)
        self.should_fail = should_fail
        self.fail_message = fail_message

    def execute(self):
        if self.should_fail:
            raise Exception(self.fail_message or "Mock execution failed")
        return {"result": "success", "task_id": self.task_run.task_id}


class ExecutionSmokeTest(TestCase):
    """执行底座冒烟测试"""

    def setUp(self):
        """测试前置准备"""
        # 创建测试租户
        self.tenant = Tenant.objects.create(
            code="test_tenant",
            name="Test Tenant",
        )

        # 注册测试 Worker
        ExecutionRegistry.register("TEST_TASK", MockWorker)

    def tearDown(self):
        """测试后清理"""
        # 清理注册表
        ExecutionRegistry._handlers.clear()

    def test_task_creation_and_status_migration(self):
        """测试任务创建和状态迁移"""
        task = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=1,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.PENDING,
        )

        # 测试状态迁移方法
        task.mark_ready()
        self.assertEqual(task.status, TaskRunStatus.READY)

        task.mark_running(worker_id="test_worker")
        self.assertEqual(task.status, TaskRunStatus.RUNNING)
        self.assertIsNotNone(task.started_at)
        self.assertEqual(task.worker_id, "test_worker")

        task.mark_success({"result": "ok"})
        self.assertEqual(task.status, TaskRunStatus.SUCCESS)
        self.assertIsNotNone(task.finished_at)
        self.assertEqual(task.output_data, {"result": "ok"})

    def test_task_failure_and_retry(self):
        """测试任务失败和重试"""
        task = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=2,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
            max_retries=3,
        )

        # 标记失败
        task.mark_failed("TEST_ERROR", "Test error message")
        self.assertEqual(task.status, TaskRunStatus.FAILED)
        self.assertEqual(task.error_code, "TEST_ERROR")

        # 测试重试判断
        self.assertTrue(task.can_retry())
        task.retry_count = 2
        self.assertTrue(task.can_retry())
        task.retry_count = 3
        self.assertFalse(task.can_retry())

    def test_task_execution_success(self):
        """测试任务执行成功"""
        task = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=3,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
        )

        # 执行任务
        execute_task_sync(task.id)

        # 刷新任务状态
        task.refresh_from_db()
        self.assertEqual(task.status, TaskRunStatus.SUCCESS)
        self.assertIsNotNone(task.finished_at)
        self.assertEqual(task.output_data["result"], "success")

    def test_task_execution_failure(self):
        """测试任务执行失败"""
        # 注册会失败的 Worker
        class FailingWorker(MockWorker):
            def execute(self):
                raise ValueError("Execution failed")

        ExecutionRegistry.register("FAILING_TASK", FailingWorker)

        task = TaskRunInstance.objects.create(
            task_type="FAILING_TASK",
            task_id=4,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
            max_retries=0,  # 不重试
        )

        # 执行任务
        execute_task_sync(task.id)

        # 刷新任务状态
        task.refresh_from_db()
        self.assertEqual(task.status, TaskRunStatus.FAILED)
        self.assertIsNotNone(task.error_message)

    def test_task_timeout(self):
        """测试任务超时"""
        task = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=5,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.RUNNING,
            started_at=timezone.now() - timezone.timedelta(seconds=100),
            timeout_seconds=60,
        )

        # 标记超时
        task.mark_timeout()
        self.assertEqual(task.status, TaskRunStatus.TIMEOUT)
        self.assertEqual(task.error_code, "TASK_TIMEOUT")

    def test_idempotency(self):
        """测试幂等性（同一任务类型+ID在同一租户下，同一时间只能有一个非终态任务）"""
        if not connection.features.supports_partial_indexes:
            self.skipTest("当前数据库不支持带条件的唯一约束")
        # 创建第一个任务
        task1 = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=6,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.RUNNING,
        )

        # 尝试创建第二个相同任务（应该违反唯一约束）
        with self.assertRaises(IntegrityError):
            TaskRunInstance.objects.create(
                task_type="TEST_TASK",
                task_id=6,
                tenant_id=self.tenant.id,
                status=TaskRunStatus.READY,
            )

        # 第一个任务完成后，可以创建新任务
        task1.mark_success({})
        task2 = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=6,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
        )
        self.assertIsNotNone(task2)

    def test_concurrent_claim(self):
        """测试并发抢占（select_for_update）"""
        task = TaskRunInstance.objects.create(
            task_type="TEST_TASK",
            task_id=7,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
        )

        # 使用 select_for_update 锁定任务
        locked_task = TaskRunInstance.objects.select_for_update().get(id=task.id)
        locked_task.mark_running(worker_id="worker1")

        # 再次尝试获取（应该获取到已更新的状态）
        task.refresh_from_db()
        self.assertEqual(task.status, TaskRunStatus.RUNNING)
        self.assertEqual(task.worker_id, "worker1")

    def test_handler_not_found(self):
        """测试未注册的 handler"""
        task = TaskRunInstance.objects.create(
            task_type="UNREGISTERED_TASK",
            task_id=8,
            tenant_id=self.tenant.id,
            status=TaskRunStatus.READY,
        )

        # 执行任务（应该失败，因为 handler 未注册）
        execute_task_sync(task.id)

        # 刷新任务状态
        task.refresh_from_db()
        self.assertEqual(task.status, TaskRunStatus.FAILED)
        self.assertEqual(task.error_code, "TASK_HANDLER_NOT_FOUND")

    def test_scheduler_tick_dispatch(self):
        """测试调度器派发"""
        # 创建多个 READY 任务
        tasks = []
        for i in range(3):
            task = TaskRunInstance.objects.create(
                task_type="TEST_TASK",
                task_id=10 + i,
                tenant_id=self.tenant.id,
                status=TaskRunStatus.READY,
            )
            tasks.append(task)

        # 派发任务（不使用 Celery，直接调用）
        dispatched = TaskDispatcher.dispatch_ready_tasks(limit=10)
        self.assertEqual(dispatched, 3)

        # 检查任务状态（应该都被执行）
        for task in tasks:
            task.refresh_from_db()
            self.assertEqual(task.status, TaskRunStatus.SUCCESS)
