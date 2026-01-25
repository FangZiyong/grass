"""
资源树子节点查询接口测试

覆盖分支（对照 task.md T4.2 验收标准）：
1. root - 查询根节点的子节点
2. folder - 查询文件夹的子节点
3. 无权限 - 未认证用户访问
4. node不存在 - 指定不存在的 parent_node_id
5. 非法scope - 传入无效的 scope 值
6. 跨租户 - 尝试访问其他租户的节点
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


class ChildrenAPITest(TestCase):
    """资源树子节点查询接口测试"""
    
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
        
        # 创建测试文件夹
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
        
        # 创建资源节点
        cls.resource_node = ResourceTreeNode.objects.create(
            tenant=cls.tenant,
            scope=ResourceScope.TABLE,
            node_type=ResourceNodeType.RESOURCE,
            name="用户表",
            parent_node=cls.folder1,
            ref_type=ResourceScope.TABLE,
            ref_resource_id=1001,
            sort_order=0,
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
        """设置认证凭证"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
    
    def test_list_root_children(self):
        """测试 root - 查询根节点的子节点"""
        self._auth()
        response = self.client.get(
            "/api/resource-trees/TABLE/children",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        
        items = data["data"]["items"]
        self.assertEqual(len(items), 2)  # folder1 和 folder2
        
        # 验证排序（按 sort_order）
        self.assertEqual(items[0]["name"], "文件夹1")
        self.assertEqual(items[1]["name"], "文件夹2")
        
        # 验证字段
        item = items[0]
        self.assertEqual(item["node_id"], self.folder1.node_id)
        self.assertEqual(item["scope"], ResourceScope.TABLE)
        self.assertEqual(item["node_type"], ResourceNodeType.FOLDER)
        self.assertEqual(item["parent_node_id"], self.table_root.node_id)
        self.assertEqual(item["order_index"], 0)
    
    def test_list_folder_children(self):
        """测试 folder - 查询文件夹的子节点"""
        self._auth()
        response = self.client.get(
            f"/api/resource-trees/TABLE/children?parent_node_id={self.folder1.node_id}",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        
        items = data["data"]["items"]
        self.assertEqual(len(items), 1)  # 只有 resource_node
        
        item = items[0]
        self.assertEqual(item["node_id"], self.resource_node.node_id)
        self.assertEqual(item["node_type"], ResourceNodeType.RESOURCE)
        self.assertEqual(item["resource_type"], ResourceScope.TABLE)
        self.assertEqual(item["resource_id"], 1001)
    
    def test_unauthenticated(self):
        """测试无权限 - 未认证用户访问（缺少认证但有租户头）"""
        # 未认证但提供租户头，应该返回 401
        response = self.client.get(
            "/api/resource-trees/TABLE/children",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn(data["code"], ["UNAUTHENTICATED", "AUTH_INVALID_TOKEN"])
    
    def test_node_not_found(self):
        """测试 node不存在 - 指定不存在的 parent_node_id"""
        self._auth()
        response = self.client.get(
            "/api/resource-trees/TABLE/children?parent_node_id=999999",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_invalid_scope(self):
        """测试非法scope - 传入无效的 scope 值"""
        self._auth()
        response = self.client.get(
            "/api/resource-trees/INVALID/children",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_SCOPE")
    
    def test_cross_tenant_access(self):
        """测试跨租户 - 尝试访问其他租户的节点"""
        self._auth()
        # 使用当前租户的上下文，尝试访问其他租户的节点
        response = self.client.get(
            f"/api/resource-trees/TABLE/children?parent_node_id={self.other_folder.node_id}",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        # 应该返回 404（节点在当前租户不存在）
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_include_resources_false(self):
        """测试 include_resources=0 仅返回文件夹"""
        self._auth()
        response = self.client.get(
            f"/api/resource-trees/TABLE/children?parent_node_id={self.folder1.node_id}&include_resources=0",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        items = data["data"]["items"]
        # folder1 下只有一个资源节点，所以应该返回空列表
        self.assertEqual(len(items), 0)
    
    def test_empty_folder(self):
        """测试空文件夹返回空列表"""
        self._auth()
        response = self.client.get(
            f"/api/resource-trees/TABLE/children?parent_node_id={self.folder2.node_id}",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        items = data["data"]["items"]
        self.assertEqual(len(items), 0)
    
    def test_different_scopes(self):
        """测试不同 scope 查询"""
        self._auth()
        # 获取 FLOW scope 的根节点
        flow_root = ResourceTreeNode.objects.get(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            parent_node=None,
        )
        
        # 创建一个 FLOW scope 的文件夹
        ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=ResourceScope.FLOW,
            node_type=ResourceNodeType.FOLDER,
            name="流程文件夹",
            parent_node=flow_root,
            sort_order=0,
            depth=1,
            path=f"/{flow_root.node_id}/",
            created_by=self.tenant_user,
            updated_by=self.tenant_user,
        )
        
        # 查询 FLOW scope
        response = self.client.get(
            "/api/resource-trees/FLOW/children",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        items = data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "流程文件夹")
        self.assertEqual(items[0]["scope"], ResourceScope.FLOW)
    
    def test_lowercase_scope(self):
        """测试小写 scope 也能正常工作"""
        self._auth()
        response = self.client.get(
            "/api/resource-trees/table/children",
            HTTP_X_TENANT_ID=str(self.tenant.tenant_id),
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
    
    def test_missing_tenant_header(self):
        """测试缺少租户头"""
        self._auth()
        response = self.client.get(
            "/api/resource-trees/TABLE/children",
        )
        
        # 缺少 X-Tenant-Id 应该返回 400
        self.assertEqual(response.status_code, 400)
