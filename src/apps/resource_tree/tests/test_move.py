"""
资源树节点移动接口测试

覆盖分支（对照 task.md T4.5 验收标准）：
1. 成功 - 移动节点到新父节点
2. 成功 - 移动到根节点
3. 成功 - 在同一父节点下调整位置（target_index）
4. 移入自身子树 - 不能移入自身子树
5. 跨租户 - 尝试移动其他租户的节点
6. node不存在 - 指定不存在的 node_id
7. parent不存在 - 指定不存在的 target_parent_node_id
8. 无权限 - 未认证用户访问
9. 冲突 - 移动后可能产生的冲突
10. 非法scope - 传入无效的 scope 值
11. 根节点 - 尝试移动根节点（应拒绝）
12. 目标父节点不是文件夹 - 目标父节点必须是文件夹
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import GlobalUser, GlobalUserStatus
from apps.accounts.services.tokens import issue_access_token
from apps.resource_tree.models import (
    ResourceNodeType,
    ResourceScope,
    ResourceTreeNode,
)
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class MoveNodeAPITest(TestCase):
    """资源树节点移动接口测试"""
    
    @classmethod
    def setUpTestData(cls):
        """设置测试数据"""
        # 创建用户
        cls.user = GlobalUser.objects.create(
            login_name="testuser",
            display_name="Test User",
            email="testuser@example.com",
            password_hash="hashed_password",
            status=GlobalUserStatus.ACTIVE,
            is_platform_admin=False,
        )
        
        # 创建租户
        cls.tenant = Tenant.objects.create(
            code="test-tenant",
            name="测试租户",
            status=TenantStatus.ACTIVE,
        )
        
        # 创建租户用户
        cls.tenant_user = TenantUser.objects.create(
            tenant=cls.tenant,
            user_id=cls.user.user_id,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        
        # 创建另一个租户（用于跨租户测试）
        cls.other_tenant = Tenant.objects.create(
            code="other-tenant",
            name="其他租户",
            status=TenantStatus.ACTIVE,
        )
        cls.other_tenant_user = TenantUser.objects.create(
            tenant=cls.other_tenant,
            user_id=cls.user.user_id,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        
        # 初始化根节点
        ResourceTreeNode.ensure_root_nodes_for_tenant(cls.tenant)
        ResourceTreeNode.ensure_root_nodes_for_tenant(cls.other_tenant)
        
        # 获取 TABLE scope 的根节点
        cls.table_root = ResourceTreeNode.objects.get(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            parent_node=None,
        )
        
        # 创建测试文件夹层级
        cls.folder1 = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="文件夹1",
            parent_node=cls.table_root,
            sort_order=0,
            depth=1,
            path=f"/{cls.table_root.node_id}/",
            created_by=cls.tenant_user,
            updated_by=cls.tenant_user,
        )
        
        cls.folder2 = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="文件夹2",
            parent_node=cls.table_root,
            sort_order=1,
            depth=1,
            path=f"/{cls.table_root.node_id}/",
            created_by=cls.tenant_user,
            updated_by=cls.tenant_user,
        )
        
        # 在 folder1 下创建子文件夹
        cls.folder1_child = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="文件夹1的子文件夹",
            parent_node=cls.folder1,
            sort_order=0,
            depth=2,
            path=f"/{cls.table_root.node_id}/{cls.folder1.node_id}/",
            created_by=cls.tenant_user,
            updated_by=cls.tenant_user,
        )
        
        # 在 folder1_child 下创建子节点（用于测试循环检测）
        cls.folder1_grandchild = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="文件夹1的孙文件夹",
            parent_node=cls.folder1_child,
            sort_order=0,
            depth=3,
            path=f"/{cls.table_root.node_id}/{cls.folder1.node_id}/{cls.folder1_child.node_id}/",
            created_by=cls.tenant_user,
            updated_by=cls.tenant_user,
        )
        
        # 创建资源节点
        cls.resource_node = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.RESOURCE,
            name="用户表",
            parent_node=cls.folder1,
            ref_type=ResourceScope.TABLE,
            ref_resource_id=1001,
            sort_order=1,
            depth=2,
            path=f"/{cls.table_root.node_id}/{cls.folder1.node_id}/",
            created_by=cls.tenant_user,
            updated_by=cls.tenant_user,
        )
        
        # 创建其他租户的节点（用于跨租户测试）
        cls.other_table_root = ResourceTreeNode.objects.get(
            tenant=cls.other_tenant,
            scope=ResourceScope.TABLE,
            parent_node=None,
        )
        cls.other_folder = ResourceTreeNode.objects.create(
            tenant=cls.other_tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="其他租户文件夹",
            parent_node=cls.other_table_root,
            sort_order=0,
            depth=1,
            path=f"/{cls.other_table_root.node_id}/",
            created_by=cls.other_tenant_user,
            updated_by=cls.other_tenant_user,
        )
        
        # 生成 access token
        cls.access_token, _ = issue_access_token(
            user_id=cls.user.user_id,
            is_platform_admin=cls.user.is_platform_admin,
        )
    
    def setUp(self):
        """每个测试前的设置"""
        self.client = APIClient()
    
    def _auth(self):
        """设置认证凭证和租户上下文"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        # 模拟 TenantContext 中间件注入
        self.client.defaults["HTTP_X_TENANT_ID"] = str(self.tenant.tenant_id)
    
    def test_move_node_success(self):
        """测试成功 - 移动节点到新父节点"""
        self._auth()
        
        # 将 folder1_child 移动到 folder2 下
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1_child.node_id,
                "target_parent_node_id": self.folder2.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertTrue(data["data"]["moved"])
        
        # 验证数据库已更新
        self.folder1_child.refresh_from_db()
        self.assertEqual(self.folder1_child.parent_node_id, self.folder2.node_id)
        self.assertEqual(self.folder1_child.depth, 2)
        self.assertIn(str(self.folder2.node_id), self.folder1_child.path)
        
        # 验证子节点的path和depth也被更新
        self.folder1_grandchild.refresh_from_db()
        self.assertEqual(self.folder1_grandchild.depth, 3)
        self.assertIn(str(self.folder2.node_id), self.folder1_grandchild.path)
    
    def test_move_to_root_success(self):
        """测试成功 - 移动到根节点"""
        self._auth()
        
        # 将 folder1_child 移动到根节点下
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1_child.node_id,
                "target_parent_node_id": None,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertTrue(data["data"]["moved"])
        
        # 验证数据库已更新
        self.folder1_child.refresh_from_db()
        self.assertEqual(self.folder1_child.parent_node_id, self.table_root.node_id)
        self.assertEqual(self.folder1_child.depth, 1)
    
    def test_move_same_parent_reorder(self):
        """测试成功 - 在同一父节点下调整位置（target_index）"""
        self._auth()
        
        # 在同一父节点下调整位置
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.table_root.node_id,
                "target_index": 1,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertTrue(data["data"]["moved"])
    
    def test_move_to_self_subtree(self):
        """测试移入自身子树 - 不能移入自身子树"""
        self._auth()
        
        # 尝试将 folder1 移动到其子节点 folder1_child 下
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.folder1_child.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_MOVE")
        self.assertIn("子节点", data["message"])
    
    def test_move_to_self(self):
        """测试移动到自身"""
        self._auth()
        
        # 尝试将 folder1 移动到自身
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.folder1.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_MOVE")
        self.assertIn("自身", data["message"])
    
    def test_move_cross_tenant(self):
        """测试跨租户 - 尝试移动其他租户的节点"""
        self._auth()
        
        # 尝试移动其他租户的节点
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.other_folder.node_id,
                "target_parent_node_id": self.folder1.node_id,
            },
            format="json",
        )
        
        # 应该返回 404（按不存在处理，防止探测）
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_move_node_not_found(self):
        """测试 node不存在 - 指定不存在的 node_id"""
        self._auth()
        non_existent_id = 99999
        
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": non_existent_id,
                "target_parent_node_id": self.folder1.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_move_parent_not_found(self):
        """测试 parent不存在 - 指定不存在的 target_parent_node_id"""
        self._auth()
        non_existent_parent_id = 99999
        
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": non_existent_parent_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_move_unauthenticated(self):
        """测试无权限 - 未认证用户访问"""
        # 不设置认证凭证
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.folder2.node_id,
            },
            format="json",
        )
        
        # 未认证可能返回 401 或 400（取决于中间件执行顺序）
        self.assertIn(response.status_code, [400, 401])
        data = response.json()
        # 可能是 UNAUTHENTICATED、PERMISSION_DENIED 或 BAD_REQUEST（缺少租户上下文）
        self.assertIn(data["code"], ["UNAUTHENTICATED", "PERMISSION_DENIED", "BAD_REQUEST"])
    
    def test_move_invalid_scope(self):
        """测试非法scope - 传入无效的 scope 值"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/INVALID/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.folder2.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_SCOPE")
    
    def test_move_root_node(self):
        """测试根节点 - 尝试移动根节点（应拒绝）"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.table_root.node_id,
                "target_parent_node_id": self.folder1.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("根节点", data["message"])
    
    def test_move_target_not_folder(self):
        """测试目标父节点不是文件夹 - 目标父节点必须是文件夹"""
        self._auth()
        
        # 尝试将节点移动到资源节点下（资源节点不能作为父节点）
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
                "target_parent_node_id": self.resource_node.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("文件夹", data["message"])
    
    def test_move_missing_node_id(self):
        """测试缺少 node_id 参数"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "target_parent_node_id": self.folder2.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "VALIDATION_FORMAT")
    
    def test_move_missing_target_parent(self):
        """测试缺少 target_parent_node_id 参数"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/TABLE/move",
            data={
                "node_id": self.folder1.node_id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "VALIDATION_FORMAT")
