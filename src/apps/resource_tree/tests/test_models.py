"""
resource_tree 模型测试

覆盖分支：
1. 创建 root - 测试 ensure_root_nodes_for_tenant 成功创建根节点
2. 重复 root - 测试幂等性，重复调用不会创建新节点
3. 创建 folder - 测试在根节点下创建文件夹
4. 层级 - 测试深层嵌套的文件夹层级
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.resource_tree.models import (
    ResourceNodeType,
    ResourceScope,
    ResourceTreeNode,
)
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class ResourceTreeNodeModelTest(TestCase):
    """ResourceTreeNode 模型测试"""

    @classmethod
    def setUpTestData(cls):
        """设置测试数据"""
        cls.tenant = Tenant.objects.create(
            code="test-tenant",
            name="测试租户",
            status=TenantStatus.ACTIVE,
        )
        cls.tenant_user = TenantUser.objects.create(
            tenant=cls.tenant,
            user_id=1,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )

    def test_create_root_nodes(self):
        """测试创建 root 节点 - ensure_root_nodes_for_tenant 成功创建根节点"""
        # 执行根节点初始化
        roots = ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        # 验证创建了 4 个根节点（每个 scope 一个）
        self.assertEqual(len(roots), 4)

        # 验证每个 scope 都有一个根节点
        scopes = {node.scope for node in roots}
        self.assertEqual(
            scopes,
            {
                ResourceScope.TABLE,
                ResourceScope.FLOW,
                ResourceScope.DATASET,
                ResourceScope.DASHBOARD,
            },
        )

        # 验证根节点属性
        for root in roots:
            self.assertEqual(root.tenant_id, self.tenant.tenant_id)
            self.assertEqual(root.name, ResourceTreeNode.ROOT_NAME)
            self.assertEqual(root.node_type, ResourceNodeType.FOLDER)
            self.assertIsNone(root.parent_node)
            self.assertEqual(root.depth, ResourceTreeNode.ROOT_DEPTH)
            self.assertEqual(root.sort_order, 0)
            self.assertIsNotNone(root.created_by)
            self.assertIsNotNone(root.updated_by)

    def test_duplicate_root_idempotent(self):
        """测试重复 root - 幂等性，重复调用不会创建新节点"""
        # 第一次创建
        roots_first = ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)
        first_ids = {node.node_id for node in roots_first}

        # 第二次调用（应该幂等）
        roots_second = ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)
        second_ids = {node.node_id for node in roots_second}

        # 验证 ID 相同（没有创建新节点）
        self.assertEqual(first_ids, second_ids)

        # 验证数量相同
        self.assertEqual(len(roots_first), len(roots_second))

        # 验证数据库中每个 scope 只有一个根节点
        for scope in ResourceScope.values:
            count = ResourceTreeNode.objects.filter(
                tenant=self.tenant,
                scope=scope,
                parent_node=None,
            ).count()
            self.assertEqual(count, 1)

    def test_create_folder(self):
        """测试创建 folder - 在根节点下创建文件夹"""
        # 先确保根节点存在
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        # 获取 TABLE scope 的根节点
        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            parent_node=None,
        )

        # 创建一个文件夹节点
        folder = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="数据表文件夹",
            parent_node=root,
            sort_order=1,
            depth=root.depth + 1,
            path=f"{root.path}{root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        # 验证文件夹创建成功
        self.assertIsNotNone(folder.node_id)
        self.assertEqual(folder.tenant_id, self.tenant.tenant_id)
        self.assertEqual(folder.scope, ResourceScope.TABLE)
        self.assertEqual(folder.node_type, ResourceNodeType.FOLDER)
        self.assertEqual(folder.name, "数据表文件夹")
        self.assertEqual(folder.parent_node_id, root.node_id)
        self.assertEqual(folder.depth, 1)

        # 验证父子关系
        self.assertIn(folder, root.children.all())

    def test_nested_hierarchy(self):
        """测试层级 - 深层嵌套的文件夹层级"""
        # 先确保根节点存在
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        # 获取 FLOW scope 的根节点
        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            parent_node=None,
        )

        # 创建多层嵌套结构：ROOT -> Level1 -> Level2 -> Level3
        level1 = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            node_type=ResourceNodeType.FOLDER,
            name="Level1",
            parent_node=root,
            sort_order=0,
            depth=1,
            path=f"/{root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        level2 = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            node_type=ResourceNodeType.FOLDER,
            name="Level2",
            parent_node=level1,
            sort_order=0,
            depth=2,
            path=f"/{root.node_id}/{level1.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        level3 = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            node_type=ResourceNodeType.FOLDER,
            name="Level3",
            parent_node=level2,
            sort_order=0,
            depth=3,
            path=f"/{root.node_id}/{level1.node_id}/{level2.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        # 验证层级深度
        self.assertEqual(root.depth, 0)
        self.assertEqual(level1.depth, 1)
        self.assertEqual(level2.depth, 2)
        self.assertEqual(level3.depth, 3)

        # 验证父子关系链
        self.assertEqual(level3.parent_node_id, level2.node_id)
        self.assertEqual(level2.parent_node_id, level1.node_id)
        self.assertEqual(level1.parent_node_id, root.node_id)
        self.assertIsNone(root.parent_node_id)

        # 验证 children 关系
        self.assertIn(level1, root.children.all())
        self.assertIn(level2, level1.children.all())
        self.assertIn(level3, level2.children.all())

    def test_unique_constraint_same_parent_same_type_same_name(self):
        """测试唯一约束 - 同父同 scope 同 node_type 同 name 不允许重复"""
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.DATASET,
            parent_node=None,
        )

        # 创建第一个文件夹
        ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.DATASET,
            node_type=ResourceNodeType.FOLDER,
            name="重复名称测试",
            parent_node=root,
            sort_order=0,
            depth=1,
            path=f"/{root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        # 尝试创建同名文件夹应该失败
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResourceTreeNode.objects.create(
                    tenant=self.tenant,
                    scope=ResourceScope.DATASET,
                    node_type=ResourceNodeType.FOLDER,
                    name="重复名称测试",
                    parent_node=root,
                    sort_order=1,
                    depth=1,
                    path=f"/{root.node_id}/",
                    created_by=self.tenant_user,
                    updated_by=self.tenant_user,
                )

    def test_create_resource_node(self):
        """测试创建资源节点（RESOURCE 类型）"""
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            parent_node=None,
        )

        # 创建资源节点（模拟挂载一个表）
        resource_node = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.RESOURCE,
            name="用户表",
            parent_node=root,
            ref_type=ResourceScope.TABLE,
            ref_resource_id=1001,
            sort_order=0,
            depth=1,
            path=f"/{root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        # 验证资源节点属性
        self.assertEqual(resource_node.node_type, ResourceNodeType.RESOURCE)
        self.assertEqual(resource_node.ref_type, ResourceScope.TABLE)
        self.assertEqual(resource_node.ref_resource_id, 1001)

    def test_soft_delete(self):
        """测试软删除标记"""
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.DASHBOARD,
            parent_node=None,
        )

        folder = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.DASHBOARD,
            node_type=ResourceNodeType.FOLDER,
            name="待删除文件夹",
            parent_node=root,
            sort_order=0,
            depth=1,
            path=f"/{root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )

        # 验证默认未删除
        self.assertFalse(folder.is_deleted)

        # 软删除
        folder.is_deleted = True
        folder.save(update_fields=["is_deleted"])

        # 重新加载验证
        folder.refresh_from_db()
        self.assertTrue(folder.is_deleted)

    def test_str_representation(self):
        """测试 __str__ 方法"""
        ResourceTreeNode.ensure_root_nodes_for_tenant(self.tenant)

        root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            parent_node=None,
        )

        str_repr = str(root)
        self.assertIn("ResourceTreeNode", str_repr)
        self.assertIn(str(root.node_id), str_repr)
        self.assertIn(ResourceScope.TABLE, str_repr)
        self.assertIn(ResourceNodeType.FOLDER, str_repr)
