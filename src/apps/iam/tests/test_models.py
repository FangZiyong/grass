"""
iam 模型测试
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.iam.models.grants import PermissionLevel, ResourceType, RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.iam.models.row_perms import RowPermission, RowPermissionStatus
from apps.tenants.models.tenant import Tenant, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class IamModelsTest(TestCase):
    """iam 模型测试"""

    def _create_tenant(self, code: str) -> Tenant:
        return Tenant.objects.create(
            code=code,
            name=f"租户-{code}",
            status=TenantStatus.ACTIVE,
        )

    def _create_tenant_user(self, tenant: Tenant, user_id: int) -> TenantUser:
        return TenantUser.objects.create(
            tenant=tenant,
            user_id=user_id,
            status=TenantUserStatus.ACTIVE,
        )

    def test_create_role(self):
        """测试创建 Role"""
        tenant = self._create_tenant("tenant-iam-1")
        actor = self._create_tenant_user(tenant, 1001)
        role = Role.objects.create(
            tenant=actor.tenant,
            code="DATA_ENGINEER",
            name="数据工程师",
            description="可管理建模与流程",
            status=RoleStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )

        self.assertIsNotNone(role.role_id)
        self.assertEqual(role.tenant_id, actor.tenant_id)
        self.assertEqual(role.status, RoleStatus.ACTIVE)

    def test_bind_role(self):
        """测试绑定角色"""
        tenant = self._create_tenant("tenant-iam-2")
        actor = self._create_tenant_user(tenant, 1002)
        member = self._create_tenant_user(tenant, 1003)
        role = Role.objects.create(
            tenant=actor.tenant,
            code="ANALYST",
            name="分析师",
            status=RoleStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )
        binding = TenantUserRole.objects.create(
            tenant=actor.tenant,
            tenant_user=member,
            role=role,
            created_by=actor,
        )

        self.assertIsNotNone(binding.tenant_user_role_id)
        self.assertEqual(binding.role_id, role.role_id)
        self.assertEqual(binding.tenant_user_id, member.tenant_user_id)

    def test_create_row_permission(self):
        """测试创建 RowPermission"""
        tenant = self._create_tenant("tenant-iam-3")
        actor = self._create_tenant_user(tenant, 1004)
        role = Role.objects.create(
            tenant=actor.tenant,
            code="VIEWER",
            name="只读",
            status=RoleStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )
        row_perm = RowPermission.objects.create(
            tenant=actor.tenant,
            role=role,
            table_id=101,
            name="仅查看自己",
            filter_dsl={
                "op": "and",
                "conditions": [
                    {"field": "owner_id", "operator": "eq", "value": {"var": "CURRENT_USER_ID"}}
                ],
            },
            status=RowPermissionStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )

        self.assertIsNotNone(row_perm.row_permission_id)
        self.assertEqual(row_perm.role_id, role.role_id)
        self.assertEqual(row_perm.status, RowPermissionStatus.ACTIVE)

    def test_unique_constraints(self):
        """测试唯一约束"""
        tenant = self._create_tenant("tenant-iam-4")
        actor = self._create_tenant_user(tenant, 1005)
        role = Role.objects.create(
            tenant=actor.tenant,
            code="OWNER",
            name="Owner",
            status=RoleStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )

        RowPermission.objects.create(
            tenant=actor.tenant,
            role=role,
            table_id=202,
            filter_dsl={"op": "and", "conditions": [{"field": "id", "operator": "gt", "value": 0}]},
            status=RowPermissionStatus.ACTIVE,
            created_by=actor,
            updated_by=actor,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RowPermission.objects.create(
                    tenant=actor.tenant,
                    role=role,
                    table_id=202,
                    filter_dsl={"op": "and", "conditions": [{"field": "id", "operator": "gt", "value": 0}]},
                    status=RowPermissionStatus.ACTIVE,
                    created_by=actor,
                    updated_by=actor,
                )

        perm = RolePermission.objects.create(
            tenant=actor.tenant,
            role=role,
            resource_type=ResourceType.FLOW,
            resource_tree_node_id=999,
            permission=PermissionLevel.MANAGE,
            created_by=actor,
            updated_by=actor,
        )
        self.assertIsNotNone(perm.role_permission_id)

