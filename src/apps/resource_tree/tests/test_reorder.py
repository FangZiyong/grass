"""
资源树同级排序接口测试

覆盖分支（对照 task.md T4.6 验收标准）：
1. 成功 - 正常重排序
2. 缺失id - ordered_node_ids 缺少部分子节点
3. 重复id - ordered_node_ids 中存在重复的节点ID
4. 跨租户 - 尝试对其他租户的节点排序
5. 无权限 - 未认证用户访问
6. 非法scope - 传入无效的 scope 值
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


class ReorderAPITest(TestCase):
    """资源树同级排序接口测试"""
    
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
        
        # 创建测试文件夹（用于排序测试）
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
        
        cls.folder3 = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="文件夹3",
            parent_node=cls.table_root,
            sort_order=2,
            depth=1,
            path=f"/{cls.table_root.node_id}/",
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
        """设置认证凭证"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
    
    def test_reorder_success(self):
        """测试成功 - 正常重排序"""
        self._auth()
        
        # 原始顺序：folder1(0), folder2(1), folder3(2)
        # 重排序为：folder3(0), folder1(1), folder2(2)
        ordered_ids = [self.folder3.node_id, self.folder1.node_id, self.folder2.node_id]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertEqual(data["data"]["updated"], 3)
        
        # 验证排序已更新
        self.folder1.refresh_from_db()
        self.folder2.refresh_from_db()
        self.folder3.refresh_from_db()
        
        self.assertEqual(self.folder3.sort_order, 0)
        self.assertEqual(self.folder1.sort_order, 1)
        self.assertEqual(self.folder2.sort_order, 2)
    
    def test_reorder_root_children(self):
        """测试对根节点的子节点排序（不传parent_node_id）"""
        self._auth()
        
        ordered_ids = [self.folder3.node_id, self.folder1.node_id, self.folder2.node_id]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertEqual(data["data"]["updated"], 3)
    
    def test_reorder_missing_ids(self):
        """测试缺失id - ordered_node_ids 缺少部分子节点"""
        self._auth()
        
        # 只包含2个节点，缺少folder3
        ordered_ids = [self.folder1.node_id, self.folder2.node_id]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("必须包含该父节点下的全部子节点", data["message"])
    
    def test_reorder_duplicate_ids(self):
        """测试重复id - ordered_node_ids 中存在重复的节点ID"""
        self._auth()
        
        # 包含重复的folder1
        ordered_ids = [self.folder1.node_id, self.folder2.node_id, self.folder1.node_id]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("重复的节点ID", data["message"])
    
    def test_reorder_extra_ids(self):
        """测试多余id - ordered_node_ids 包含不属于该父节点的节点"""
        self._auth()
        
        # 包含一个不存在的节点ID
        ordered_ids = [self.folder1.node_id, self.folder2.node_id, self.folder3.node_id, 999999]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("不匹配", data["message"])
    
    def test_reorder_cross_tenant(self):
        """测试跨租户 - 尝试对其他租户的节点排序"""
        self._auth()
        
        # 尝试使用其他租户的节点ID
        ordered_ids = [self.other_folder.node_id]
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": ordered_ids,
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("不属于该父节点或租户/scope", data["message"])
    
    def test_reorder_unauthenticated(self):
        """测试无权限 - 未认证用户访问"""
        # 未认证但提供租户头，应该返回 401
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": [self.folder1.node_id, self.folder2.node_id, self.folder3.node_id],
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn(data["code"], ["UNAUTHENTICATED", "AUTH_INVALID_TOKEN"])
    
    def test_reorder_invalid_scope(self):
        """测试非法scope - 传入无效的 scope 值"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/INVALID/reorder",
            {
                "parent_node_id": self.table_root.node_id,
                "ordered_node_ids": [self.folder1.node_id, self.folder2.node_id, self.folder3.node_id],
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_SCOPE")
    
    def test_reorder_parent_not_found(self):
        """测试父节点不存在"""
        self._auth()
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": 999999,
                "ordered_node_ids": [],
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_reorder_empty_list(self):
        """测试空列表（父节点下没有子节点）"""
        self._auth()
        
        # 创建一个没有子节点的文件夹
        empty_folder = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="空文件夹",
            parent_node=self.table_root,
            sort_order=10,
            depth=1,
            path=f"/{self.table_root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": empty_folder.node_id,
                "ordered_node_ids": [],
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertEqual(data["data"]["updated"], 0)
    
    def test_reorder_single_node(self):
        """测试单个节点排序"""
        self._auth()
        
        # 创建一个只有一个子节点的文件夹
        parent_folder = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="父文件夹",
            parent_node=self.table_root,
            sort_order=10,
            depth=1,
            path=f"/{self.table_root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )
        
        child_folder = ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.FOLDER,
            name="子文件夹",
            parent_node=parent_folder,
            sort_order=0,
            depth=2,
            path=f"/{self.table_root.node_id}/{parent_folder.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )
        
        response = self.client.post(
            "/api/resource-trees/TABLE/reorder",
            {
                "parent_node_id": parent_folder.node_id,
                "ordered_node_ids": [child_folder.node_id],
            },
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        self.assertEqual(data["data"]["updated"], 1)
        
        # 验证排序已更新
        child_folder.refresh_from_db()
        self.assertEqual(child_folder.sort_order, 0)