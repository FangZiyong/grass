"""
角色管理接口测试
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.services.tokens import issue_access_token
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class RoleAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            code="tenant-roles",
            name="租户-角色",
            status=TenantStatus.ACTIVE,
        )
        self.owner = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=1001,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.member = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=1002,
            status=TenantUserStatus.ACTIVE,
            is_owner=False,
        )
        self.role = Role.objects.create(
            tenant=self.tenant,
            code="ANALYST",
            name="分析师",
            description="分析角色",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_list_roles_success(self):
        """角色列表可分页返回"""
        self._auth(self.owner.user_id)
        response = self.client.get(
            "/api/roles",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["role_id"], self.role.role_id)

    def test_list_roles_permission_denied(self):
        """非 Owner 无权限访问"""
        self._auth(self.member.user_id)
        response = self.client.get(
            "/api/roles",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_create_role_success(self):
        """创建角色"""
        self._auth(self.owner.user_id)
        payload = {"name": "数据工程师", "description": "可管理建模"}
        response = self.client.post(
            "/api/roles",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertEqual(response.data["data"]["role"]["code"], "ROLE_1000")

    def test_create_role_name_conflict(self):
        """角色名称冲突返回 409"""
        self._auth(self.owner.user_id)
        payload = {"name": "分析师"}
        response = self.client.post(
            "/api/roles",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ROLE_NAME_CONFLICT")

    def test_create_role_auto_increment(self):
        """自动生成的角色编码在租户内递增"""
        self._auth(self.owner.user_id)

        r1 = self.client.post(
            "/api/roles",
            data={"name": "数据工程师"},
            format="json",
            **self._tenant_header(),
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["data"]["role"]["code"], "ROLE_1000")

        r2 = self.client.post(
            "/api/roles",
            data={"name": "报表查看者"},
            format="json",
            **self._tenant_header(),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["data"]["role"]["code"], "ROLE_1001")

    def test_update_role_success(self):
        """更新角色名称"""
        self._auth(self.owner.user_id)
        response = self.client.patch(
            f"/api/roles/{self.role.role_id}",
            data={"name": "高级分析师"},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["role"]["name"], "高级分析师")

    def test_update_role_not_found(self):
        """更新不存在角色返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.patch(
            "/api/roles/99999",
            data={"name": "不存在"},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_delete_role_in_use(self):
        """角色被成员绑定时禁止删除"""
        self._auth(self.owner.user_id)
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role,
            created_by=self.owner,
        )

        response = self.client.delete(
            f"/api/roles/{self.role.role_id}",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ROLE_IN_USE")

    def test_delete_role_builtin(self):
        """内置角色不可删除"""
        self._auth(self.owner.user_id)
        builtin_role = Role.objects.create(
            tenant=self.tenant,
            code="OWNER",
            name="Owner",
            is_builtin=True,
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

        response = self.client.delete(
            f"/api/roles/{builtin_role.role_id}",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "ROLE_BUILTIN_CANNOT_DELETE")
