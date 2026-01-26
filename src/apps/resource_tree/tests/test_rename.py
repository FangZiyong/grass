"""
资源树节点重命名接口测试

覆盖分支（对照 task.md T4.4 验收标准）：
1. 成功 - 重命名文件夹节点
2. 成功 - 重命名资源节点
3. 冲突 - 同级节点已存在同名
4. 无权限 - 未认证用户访问
5. not found - 指定不存在的 node_id
6. 跨租户 - 尝试重命名其他租户的节点
7. 非法scope - 传入无效的 scope 值
8. 根节点 - 尝试重命名根节点（应拒绝）
9. 名称长度 - 名称长度超出限制
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


class RenameNodeAPITest(TestCase):
    """资源树节点重命名接口测试"""
    
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
        """设置认证凭证和租户上下文"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        # 模拟 TenantContext 中间件注入
        self.client.defaults["HTTP_X_TENANT_ID"] = str(self.tenant.tenant_id)
    
    def test_rename_folder_success(self):
        """测试成功 - 重命名文件夹节点"""
        self._auth()
        new_name = "新文件夹名"
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": new_name},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        
        node_data = data["data"]["node"]
        self.assertEqual(node_data["name"], new_name)
        self.assertEqual(node_data["node_id"], self.folder1.node_id)
        
        # 验证数据库已更新
        self.folder1.refresh_from_db()
        self.assertEqual(self.folder1.name, new_name)
    
    def test_rename_resource_success(self):
        """测试成功 - 重命名资源节点"""
        self._auth()
        new_name = "新表名"
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.resource_node.node_id}",
            data={"name": new_name},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        
        node_data = data["data"]["node"]
        self.assertEqual(node_data["name"], new_name)
        self.assertEqual(node_data["node_id"], self.resource_node.node_id)
        
        # 验证数据库已更新
        self.resource_node.refresh_from_db()
        self.assertEqual(self.resource_node.name, new_name)
    
    def test_rename_name_conflict(self):
        """测试冲突 - 同级节点已存在同名"""
        self._auth()
        # folder2 已经存在，尝试将 folder1 重命名为 folder2 的名称
        new_name = self.folder2.name
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": new_name},
            format="json",
        )
        
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["code"], "NAME_CONFLICT")
        self.assertIn("同名", data["message"])
        
        # 验证数据库未更新
        self.folder1.refresh_from_db()
        self.assertNotEqual(self.folder1.name, new_name)
    
    def test_rename_unauthenticated(self):
        """测试无权限 - 未认证用户访问"""
        # 不设置认证凭证
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": "新名称"},
            format="json",
        )
        
        # 未认证可能返回 401 或 400（取决于中间件执行顺序）
        self.assertIn(response.status_code, [400, 401])
        data = response.json()
        # 可能是 UNAUTHENTICATED、PERMISSION_DENIED 或 BAD_REQUEST（缺少租户上下文）
        self.assertIn(data["code"], ["UNAUTHENTICATED", "PERMISSION_DENIED", "BAD_REQUEST"])
    
    def test_rename_node_not_found(self):
        """测试 not found - 指定不存在的 node_id"""
        self._auth()
        non_existent_id = 99999
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{non_existent_id}",
            data={"name": "新名称"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_rename_cross_tenant(self):
        """测试跨租户 - 尝试重命名其他租户的节点"""
        self._auth()
        # 尝试重命名其他租户的节点
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.other_folder.node_id}",
            data={"name": "新名称"},
            format="json",
        )
        
        # 应该返回 404（按不存在处理，防止探测）
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], "RESOURCE_NODE_NOT_FOUND")
    
    def test_rename_invalid_scope(self):
        """测试非法scope - 传入无效的 scope 值"""
        self._auth()
        
        response = self.client.patch(
            f"/api/resource-trees/INVALID/nodes/{self.folder1.node_id}",
            data={"name": "新名称"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "INVALID_SCOPE")
    
    def test_rename_root_node(self):
        """测试根节点 - 尝试重命名根节点（应拒绝）"""
        self._auth()
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.table_root.node_id}",
            data={"name": "新根节点名"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "BAD_REQUEST")
        self.assertIn("根节点", data["message"])
    
    def test_rename_name_too_long(self):
        """测试名称长度 - 名称长度超出限制"""
        self._auth()
        # 创建超过64字符的名称
        long_name = "a" * 65
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": long_name},
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        # 可能是序列化器校验失败或服务层校验失败
        self.assertIn(data["code"], ["VALIDATION_FORMAT", "BAD_REQUEST"])
    
    def test_rename_empty_name(self):
        """测试空名称"""
        self._auth()
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": ""},
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn(data["code"], ["VALIDATION_FORMAT", "BAD_REQUEST"])
    
    def test_rename_same_name(self):
        """测试重命名为相同名称（应该成功，不做实际更新）"""
        self._auth()
        original_name = self.folder1.name
        
        response = self.client.patch(
            f"/api/resource-trees/TABLE/nodes/{self.folder1.node_id}",
            data={"name": original_name},
            format="json",
        )
        
        # 应该成功（虽然名称未变化）
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["code"], "OK")
        
        node_data = data["data"]["node"]
        self.assertEqual(node_data["name"], original_name)
