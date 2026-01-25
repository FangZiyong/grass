"""
成员绑定角色接口测试
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.services.tokens import issue_access_token
from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class MemberRoleBindingAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            code="tenant-membership",
            name="租户-成员角色",
            status=TenantStatus.ACTIVE,
        )
        self.owner_user = GlobalUser.objects.create(
            login_name="owner_user",
            display_name="Owner User",
            email="owner@example.com",
            password_hash="hash",
            status=GlobalUserStatus.ACTIVE,
        )
        self.member_user = GlobalUser.objects.create(
            login_name="member_user",
            display_name="Member User",
            email="member@example.com",
            password_hash="hash",
            status=GlobalUserStatus.ACTIVE,
        )
        self.owner = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=self.owner_user.user_id,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )
        self.member = TenantUser.objects.create(
            tenant=self.tenant,
            user_id=self.member_user.user_id,
            status=TenantUserStatus.ACTIVE,
            is_owner=False,
        )
        self.role_1 = Role.objects.create(
            tenant=self.tenant,
            code="ANALYST",
            name="分析师",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.role_2 = Role.objects.create(
            tenant=self.tenant,
            code="ENGINEER",
            name="工程师",
            status=RoleStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

        self.other_tenant = Tenant.objects.create(
            code="tenant-other",
            name="其他租户",
            status=TenantStatus.ACTIVE,
        )
        self.other_global_user = GlobalUser.objects.create(
            login_name="other_user",
            display_name="Other User",
            email="other@example.com",
            password_hash="hash",
            status=GlobalUserStatus.ACTIVE,
        )
        self.other_user = TenantUser.objects.create(
            tenant=self.other_tenant,
            user_id=self.other_global_user.user_id,
            status=TenantUserStatus.ACTIVE,
            is_owner=True,
        )

    def _auth(self, user_id: int):
        token, _ = issue_access_token(user_id=user_id, is_platform_admin=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _tenant_header(self):
        return {"HTTP_X_TENANT_ID": str(self.tenant.tenant_id)}

    def test_bind_roles_success(self):
        """Owner 可为成员绑定角色"""
        self._auth(self.owner.user_id)
        payload = {"role_ids": [self.role_1.role_id, self.role_2.role_id]}

        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/roles",
            data=payload,
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertEqual(response.data["data"]["role_ids"], payload["role_ids"])
        self.assertEqual(
            TenantUserRole.objects.filter(
                tenant=self.tenant, tenant_user=self.member
            ).count(),
            2,
        )

    def test_bind_roles_idempotent(self):
        """重复绑定不报错"""
        self._auth(self.owner.user_id)
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role_1,
            created_by=self.owner,
        )

        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/roles",
            data={"role_ids": [self.role_1.role_id]},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertEqual(
            TenantUserRole.objects.filter(
                tenant=self.tenant, tenant_user=self.member, role=self.role_1
            ).count(),
            1,
        )

    def test_bind_roles_permission_denied(self):
        """非 Owner 禁止绑定"""
        self._auth(self.member.user_id)
        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/roles",
            data={"role_ids": [self.role_1.role_id]},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_bind_roles_tenant_user_not_found(self):
        """跨租户成员返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.post(
            f"/api/users/{self.other_user.tenant_user_id}/roles",
            data={"role_ids": [self.role_1.role_id]},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "TENANT_USER_NOT_FOUND")

    def test_bind_roles_role_not_found(self):
        """不存在角色返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/roles",
            data={"role_ids": [999999]},
            format="json",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "ROLE_NOT_FOUND")

    def test_unbind_role_success(self):
        """解绑角色成功"""
        self._auth(self.owner.user_id)
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role_1,
            created_by=self.owner,
        )

        response = self.client.delete(
            f"/api/users/{self.member.tenant_user_id}/roles/{self.role_1.role_id}",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertTrue(response.data["data"]["deleted"])
        self.assertFalse(
            TenantUserRole.objects.filter(
                tenant=self.tenant, tenant_user=self.member, role=self.role_1
            ).exists()
        )

    def test_get_role_users_success(self):
        """查询角色成员列表"""
        self._auth(self.owner.user_id)
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role_1,
            created_by=self.owner,
        )

        response = self.client.get(
            f"/api/roles/{self.role_1.role_id}/users",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        data = response.data["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["tenant_user_id"], self.member.tenant_user_id)
        self.assertEqual(data["items"][0]["email"], self.member_user.email)

    def test_get_role_users_permission_denied(self):
        """非 Owner 禁止查询角色成员"""
        self._auth(self.member.user_id)
        response = self.client.get(
            f"/api/roles/{self.role_1.role_id}/users",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_get_member_roles_success(self):
        """查询成员角色列表"""
        self._auth(self.owner.user_id)
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role_1,
            created_by=self.owner,
        )
        TenantUserRole.objects.create(
            tenant=self.tenant,
            tenant_user=self.member,
            role=self.role_2,
            created_by=self.owner,
        )

        response = self.client.get(
            f"/api/users/{self.member.tenant_user_id}/roles",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        role_ids = {item["role_id"] for item in response.data["data"]["roles"]}
        self.assertEqual(role_ids, {self.role_1.role_id, self.role_2.role_id})

    def test_get_member_roles_not_found(self):
        """成员不存在返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.get(
            f"/api/users/{self.other_user.tenant_user_id}/roles",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "TENANT_USER_NOT_FOUND")

    def test_set_owner_success(self):
        """设为 Owner 成功"""
        self._auth(self.owner.user_id)
        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertTrue(response.data["data"]["is_owner"])
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_owner)

    def test_set_owner_permission_denied(self):
        """非 Owner 禁止设为 Owner"""
        self._auth(self.member.user_id)
        response = self.client.post(
            f"/api/users/{self.member.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_set_owner_tenant_user_not_found(self):
        """跨租户成员设为 Owner 返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.post(
            f"/api/users/{self.other_user.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "TENANT_USER_NOT_FOUND")

    def test_unset_owner_success(self):
        """取消 Owner 成功"""
        self._auth(self.owner.user_id)
        self.member.is_owner = True
        self.member.save(update_fields=["is_owner", "updated_at"])

        response = self.client.delete(
            f"/api/users/{self.member.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["code"], "OK")
        self.assertFalse(response.data["data"]["is_owner"])
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_owner)

    def test_unset_owner_min_one_violation(self):
        """至少保留 1 名 Owner"""
        self._auth(self.owner.user_id)
        response = self.client.delete(
            f"/api/users/{self.owner.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "OWNER_MIN_ONE_VIOLATION")

    def test_unset_owner_tenant_user_not_found(self):
        """跨租户成员取消 Owner 返回 404"""
        self._auth(self.owner.user_id)
        response = self.client.delete(
            f"/api/users/{self.other_user.tenant_user_id}/owner",
            **self._tenant_header(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "TENANT_USER_NOT_FOUND")

