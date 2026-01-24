"""
T3.5 角色资源授权接口测试
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.services.tokens import issue_access_token
from apps.iam.models.grants import PermissionLevel, ResourceType, RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
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

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_get_role_resource_permissions_success(self):
        """可查询角色资源授权"""
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.FLOW,
            resource_tree_node_id=101,
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
        self.assertEqual(items[0]["resource_tree_node_id"], 101)
        self.assertEqual(items[0]["resource_type"], ResourceType.FLOW)
        self.assertEqual(items[0]["permission_level"], PermissionLevel.MANAGE)
        self.assertEqual(items[0]["is_inherited"], False)

    def test_put_role_resource_permissions_overwrite(self):
        """PUT 按 resource_type 全量覆盖"""
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role,
            resource_type=ResourceType.DATASET,
            resource_tree_node_id=201,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self._auth(self.owner.user_id)
        payload = {
            "items": [
                {
                    "resource_tree_node_id": 202,
                    "resource_type": ResourceType.DATASET,
                    "permission_level": PermissionLevel.EDIT,
                },
                {
                    "resource_tree_node_id": 203,
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
        self.assertFalse(perms.filter(resource_tree_node_id=201).exists())

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

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_get_permission_panel_success(self):
        """权限面板返回角色授权与我的权限"""
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role_viewer,
            resource_type=ResourceType.DATASET,
            resource_tree_node_id=701,
            permission=PermissionLevel.VIEW,
            created_by=self.owner,
            updated_by=self.owner,
        )
        RolePermission.objects.create(
            tenant=self.tenant,
            role=self.role_admin,
            resource_type=ResourceType.DATASET,
            resource_tree_node_id=701,
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
            "/api/permissions/resources/701",
            data={"scope": "DATASET"},
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["data"]
        self.assertEqual(payload["resource_node_id"], 701)
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

