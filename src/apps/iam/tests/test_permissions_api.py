"""
角色资源授权接口测试
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.services.tokens import issue_access_token
from apps.iam.models.grants import PermissionLevel, ResourceType, RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.resource_tree.models.resource_node import ResourceScope, ResourceTreeNode
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class RoleResourcePermissionsAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            code="tenant-permissions",
            name="租户-权限",
            status=TenantStatus.ACTIVE,
        )
        self.owner = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=2001,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.member = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=2002,
            status=TenantUserStatus.ACTIVE,
            is_owner=False,
        )
        self.role = Role.objects.create(
            tenant=self.tenant,
            code="ANALYST",
            name="分析师",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _create_tree_node(self, scope: str = ResourceScope.FLOW, name: str = "test-node"):
        """创建资源树节点用于测试"""
        return ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=scope,
            name=name,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_get_role_resource_permissions_success(self):
        """可查询角色资源授权"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="flow-node")
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.FLOW,
            resource_tree_node=node,
            permission=PermissionLevel.MANAGE,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)

        response = self.client.get(
            f"/api/roles/{self.role.role_id}/resource-permissions",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["resource_tree_node_id"], node.node_id)
        self.assertEqual(items[0]["resource_type"], ResourceType.FLOW)
        self.assertEqual(items[0]["permission_level"], PermissionLevel.MANAGE)
        self.assertEqual(items[0]["is_inherited"], False)

    def test_put_role_resource_permissions_overwrite(self):
        """PUT 按 resource_type 全量覆盖"""
        node1 = self._create_tree_node(scope=ResourceScope.DATASET, name="dataset-node-1")
        node2 = self._create_tree_node(scope=ResourceScope.DATASET, name="dataset-node-2")
        node3 = self._create_tree_node(scope=ResourceScope.DATASET, name="dataset-node-3")
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.DATASET,
            resource_tree_node=node1,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)
        payload = {
            "items": [
                {
                    "resource_tree_node_id": node2.node_id,
                    "resource_type": ResourceType.DATASET,
                    "permission_level": PermissionLevel.EDIT,
                },
                {
                    "resource_tree_node_id": node3.node_id,
                    "resource_type": ResourceType.DATASET,
                    "permission_level": PermissionLevel.VIEW,
                },
            ]
        }

        response = self.client.put(
            f"/api/roles/{self.role.role_id}/resource-permissions",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["updated"], 2)
        perms = RolePermission.objects.filter(
            tenant=self.tenant, role=self.role, resource_type=ResourceType.DATASET
        )
        self.assertEqual(perms.count(), 2)
        self.assertFalse(perms.filter(resource_tree_node_id=node1.node_id).exists())

    def test_put_role_resource_permissions_invalid_level(self):
        """不支持 RUN 权限等级"""
        self._auth(self.owner.user_id)
        payload = {
            "items": [
                {
                    "resource_tree_node_id": 301,
                    "resource_type": ResourceType.FLOW,
                    "permission_level": "RUN",
                }
            ]
        }

        response = self.client.put(
            f"/api/roles/{self.role.role_id}/resource-permissions",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "BAD_REQUEST")

    def test_get_role_resource_permissions_permission_denied(self):
        """非 Owner 无权限"""
        self._auth(self.member.user_id)
        response = self.client.get(
            f"/api/roles/{self.role.role_id}/resource-permissions",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_put_role_resource_permissions_role_not_found(self):
        """角色不存在返回 404"""
        self._auth(self.owner.user_id)
        payload = {
            "items": [
                {
                    "resource_tree_node_id": 401,
                    "resource_type": ResourceType.FLOW,
                    "permission_level": PermissionLevel.VIEW,
                }
            ]
        }

        response = self.client.put(
            "/api/roles/99999/resource-permissions",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")


class PermissionPanelAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            code="tenant-permission-panel",
            name="租户-权限面板",
            status=TenantStatus.ACTIVE,
        )
        self.owner = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=3001,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.role_viewer = Role.objects.create(
            tenant=self.tenant,
            code="VIEWER",
            name="查看者",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.role_admin = Role.objects.create(
            tenant=self.tenant,
            code="ADMIN",
            name="管理员",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _create_tree_node(self, scope: str = ResourceScope.DATASET, name: str = "test-node"):
        """创建资源树节点用于测试"""
        return ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=scope,
            name=name,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_get_permission_panel_success(self):
        """权限面板返回角色授权与我的权限"""
        node = self._create_tree_node(scope=ResourceScope.DATASET, name="panel-test-node")
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role_viewer,
            resource_type=ResourceType.DATASET,
            resource_tree_node=node,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role_admin,
            resource_type=ResourceType.DATASET,
            resource_tree_node=node,
            permission=PermissionLevel.MANAGE,
            created_by=self.owner,
            updated_by=self.owner,
        )
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.owner,
            role=self.role_viewer,
            created_by=self.owner,
        )
        self._auth(self.owner.user_id)

        response = self.client.get(
            f"/api/permissions/resources/{node.node_id}",
            data={"scope": "DATASET"},
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertEqual(payload["resource_node_id"], node.node_id)
        self.assertEqual(len(payload["role_grants"]), 2)
        self.assertEqual(payload["my_effective_permission"], PermissionLevel.VIEW)
        self.assertTrue(payload["can_manage"])

    def test_get_permission_panel_table_missing_resource_type(self):
        """TABLE scope 缺少 resource_type"""
        self._auth(self.owner.user_id)
        response = self.client.get(
            "/api/permissions/resources/702",
            data={"scope": "TABLE"},
            **self._tenant_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "BAD_REQUEST")

    def test_get_permission_panel_invalid_scope(self):
        """非法 scope 返回 400"""
        self._auth(self.owner.user_id)
        response = self.client.get(
            "/api/permissions/resources/703",
            data={"scope": "INVALID"},
            **self._tenant_header(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "BAD_REQUEST")


class GrantsAPITest(TestCase):
    """授权接口测试"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            code="tenant-grants",
            name="租户-授权",
            status=TenantStatus.ACTIVE,
        )
        self.tenant2 = Tenant.objects.create(
            code="tenant-grants-2",
            name="租户-授权2",
            status=TenantStatus.ACTIVE,
        )
        self.owner = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=4001,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.member = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=4002,
            status=TenantUserStatus.ACTIVE,
            is_owner=False,
        )
        self.owner2 = TenantUser.objects.create(
            tenant=self.tenant2,
            user_id=4003,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.role = Role.objects.create(
            tenant=self.tenant,
            code="ANALYST",
            name="分析师",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _create_tree_node(self, scope: str = ResourceScope.FLOW, name: str = "test-node"):
        """创建资源树节点用于测试"""
        return ResourceTreeNode.objects.create(
            tenant=self.tenant,
            scope=scope,
            name=name,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self, tenant=None):
        t = tenant or self.tenant
        return {"HTTP_X_TENANT_ID": str(t.tenant_id)}

    def test_create_grant_success(self):
        """创建授权成功"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="grant-node")
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.FLOW,
            "resource_tree_node_id": node.node_id,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.EDIT,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        grant_id = response.data["data"]["grant_id"]
        self.assertGreater(grant_id, 0)
        # 验证数据库记录
        perm = RolePermission.objects.get(role_permission_id=grant_id)
        self.assertEqual(perm.role_id, self.role.role_id)
        self.assertEqual(perm.resource_tree_node_id, node.node_id)
        self.assertEqual(perm.permission, PermissionLevel.EDIT)

    def test_update_grant_success(self):
        """更新授权成功"""
        node = self._create_tree_node(scope=ResourceScope.DATASET, name="update-grant-node")
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.DATASET,
            resource_tree_node=node,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.DATASET,
            "resource_tree_node_id": node.node_id,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.MANAGE,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        grant_id = response.data["data"]["grant_id"]
        self.assertGreater(grant_id, 0)
        # 验证权限已更新
        perm = RolePermission.objects.get(role_permission_id=grant_id)
        self.assertEqual(perm.permission, PermissionLevel.MANAGE)

    def test_delete_grant_via_none_permission(self):
        """permission_level=NONE 时删除授权"""
        node = self._create_tree_node(scope=ResourceScope.DASHBOARD, name="delete-via-none-node")
        perm = RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.DASHBOARD,
            resource_tree_node=node,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.DASHBOARD,
            "resource_tree_node_id": node.node_id,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.NONE,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["grant_id"], 0)
        # 验证记录已删除
        self.assertFalse(
            RolePermission.objects.filter(role_permission_id=perm.role_permission_id).exists()
        )

    def test_revoke_grant_success(self):
        """DELETE 撤销授权成功"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="revoke-node")
        perm = RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.FLOW,
            resource_tree_node=node,
            permission=PermissionLevel.EDIT,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)

        response = self.client.delete(
            f"/api/permissions/grants/{perm.role_permission_id}",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["deleted"])
        # 验证记录已删除
        self.assertFalse(
            RolePermission.objects.filter(role_permission_id=perm.role_permission_id).exists()
        )

    def test_create_grant_permission_denied(self):
        """非 Owner 无权限创建授权"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="perm-denied-node")
        self._auth(self.member.user_id)
        payload = {
            "scope": ResourceScope.FLOW,
            "resource_tree_node_id": node.node_id,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.VIEW,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_revoke_grant_permission_denied(self):
        """非 Owner 无权限撤销授权"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="revoke-denied-node")
        perm = RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.FLOW,
            resource_tree_node=node,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.member.user_id)

        response = self.client.delete(
            f"/api/permissions/grants/{perm.role_permission_id}",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_create_grant_role_not_found(self):
        """角色不存在返回 404"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="role-not-found-node")
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.FLOW,
            "resource_tree_node_id": node.node_id,
            "role_id": 99999,
            "permission_level": PermissionLevel.VIEW,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_create_grant_resource_node_not_found(self):
        """资源节点不存在返回 404"""
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.FLOW,
            "resource_tree_node_id": 99999,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.VIEW,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "RESOURCE_NODE_NOT_FOUND")

    def test_revoke_grant_not_found(self):
        """授权记录不存在返回 404"""
        self._auth(self.owner.user_id)

        response = self.client.delete(
            "/api/permissions/grants/99999",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "GRANT_NOT_FOUND")

    def test_create_grant_table_scope_requires_resource_type(self):
        """TABLE scope 必须提供 resource_type"""
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.TABLE,
            "resource_tree_node_id": 1,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.VIEW,
        }

        response = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "BAD_REQUEST")

    def test_create_grant_idempotent(self):
        """幂等性：重复创建相同授权返回同一 grant_id"""
        node = self._create_tree_node(scope=ResourceScope.FLOW, name="idempotent-node")
        self._auth(self.owner.user_id)
        payload = {
            "scope": ResourceScope.FLOW,
            "resource_tree_node_id": node.node_id,
            "role_id": self.role.role_id,
            "permission_level": PermissionLevel.VIEW,
        }

        response1 = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )
        response2 = self.client.post(
            "/api/permissions/grants",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["data"]["grant_id"], response2.data["data"]["grant_id"])
        # 验证只有一条记录
        count = RolePermission.objects.filter(
            tenant=self.tenant,
            role=self.role,
            resource_tree_node=node,
            resource_type=ResourceType.FLOW,
        ).count()
        self.assertEqual(count, 1)

