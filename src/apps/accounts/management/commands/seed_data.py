"""
数据生成脚本：创建测试数据

用法：
    python manage.py seed_data
    python manage.py seed_data --users 10 --tenants 3
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models.users import GlobalUser, GlobalUserStatus
from apps.iam.models.grants import PermissionLevel, ResourceType, RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role, RoleStatus
from apps.resource_tree.models.resource_node import (
    ResourceNodeType,
    ResourceScope,
    ResourceTreeNode,
)
from apps.tenants.models.tenant import Tenant, TenantPlan, TenantStatus
from apps.tenants.models.tenant_user import TenantUser, TenantUserStatus


class Command(BaseCommand):
    help = "生成测试数据：用户、租户、角色、资源树、权限等"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="要创建的用户数量（默认：10）",
        )
        parser.add_argument(
            "--tenants",
            type=int,
            default=3,
            help="要创建的租户数量（默认：3）",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="清空现有数据后再生成",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        num_tenants = options["tenants"]
        clear_data = options["clear"]

        self.stdout.write(self.style.WARNING("开始生成测试数据..."))

        with transaction.atomic():
            if clear_data:
                self._clear_existing_data()

            # 1. 创建全局用户
            users = self._create_users(num_users)
            self.stdout.write(
                self.style.SUCCESS(f"✓ 创建了 {len(users)} 个用户")
            )

            # 2. 创建租户
            tenants = self._create_tenants(num_tenants)
            self.stdout.write(
                self.style.SUCCESS(f"✓ 创建了 {len(tenants)} 个租户")
            )

            # 3. 为每个租户创建成员关系
            tenant_users_map = {}
            for tenant in tenants:
                tenant_users = self._create_tenant_users(tenant, users)
                tenant_users_map[tenant.tenant_id] = tenant_users
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 租户 {tenant.code} 添加了 {len(tenant_users)} 个成员"
                    )
                )

            # 4. 为每个租户创建角色
            roles_map = {}
            for tenant in tenants:
                roles = self._create_roles(tenant, tenant_users_map[tenant.tenant_id])
                roles_map[tenant.tenant_id] = roles
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 租户 {tenant.code} 创建了 {len(roles)} 个角色"
                    )
                )

            # 5. 为每个租户分配成员角色
            for tenant in tenants:
                tenant_users = tenant_users_map[tenant.tenant_id]
                roles = roles_map[tenant.tenant_id]
                self._assign_roles(tenant, tenant_users, roles)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ 租户 {tenant.code} 分配了角色")
                )

            # 6. 为每个租户创建资源树
            resource_nodes_map = {}
            for tenant in tenants:
                owner = tenant_users_map[tenant.tenant_id][0]
                nodes = self._create_resource_tree(tenant, owner)
                resource_nodes_map[tenant.tenant_id] = nodes
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ 租户 {tenant.code} 创建了 {len(nodes)} 个资源树节点"
                    )
                )

            # 7. 为每个租户的角色配置权限
            for tenant in tenants:
                roles = roles_map[tenant.tenant_id]
                nodes = resource_nodes_map[tenant.tenant_id]
                owner = tenant_users_map[tenant.tenant_id][0]
                self._assign_permissions(tenant, roles, nodes, owner)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ 租户 {tenant.code} 配置了权限")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"数据生成完成！\n"
                f"  - 用户数：{len(users)}\n"
                f"  - 租户数：{len(tenants)}\n"
                f"  - 登录账号：user1/user1user1, user2/user2user2, ...\n"
                f"{'='*60}"
            )
        )

    def _clear_existing_data(self):
        """清空现有数据"""
        self.stdout.write(self.style.WARNING("清空现有数据..."))
        RolePermission.objects.all().delete()
        TenantUserRole.objects.all().delete()
        ResourceTreeNode.objects.all().delete()
        Role.objects.all().delete()
        TenantUser.objects.all().delete()
        Tenant.objects.all().delete()
        GlobalUser.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✓ 数据已清空"))

    def _create_users(self, num_users):
        """创建全局用户"""
        users = []
        for i in range(1, num_users + 1):
            login_name = f"user{i}"
            password = f"user{i}user{i}"
            
            user, created = GlobalUser.objects.get_or_create(
                login_name=login_name,
                defaults={
                    "display_name": f"用户{i}",
                    "email": f"user{i}@example.com",
                    "password_hash": make_password(password),
                    "status": GlobalUserStatus.ACTIVE,
                    "is_platform_admin": i == 1,  # user1 是平台管理员
                },
            )
            
            if not created:
                # 如果用户已存在，更新密码
                user.password_hash = make_password(password)
                user.save(update_fields=["password_hash"])
            
            users.append(user)
        
        return users

    def _create_tenants(self, num_tenants):
        """创建租户"""
        tenants = []
        plans = [TenantPlan.BASIC, TenantPlan.PRO, TenantPlan.ENTERPRISE]
        
        for i in range(1, num_tenants + 1):
            tenant, _ = Tenant.objects.get_or_create(
                name=f"租户{i}",
                defaults={
                    "status": TenantStatus.ACTIVE,
                    "plan": plans[(i - 1) % len(plans)],
                },
            )
            tenants.append(tenant)
        
        return tenants

    def _create_tenant_users(self, tenant, users):
        """为租户添加成员"""
        tenant_users = []
        
        # 为每个租户添加前5个用户（或所有用户，取较小值）
        num_members = min(5, len(users))
        for i, user in enumerate(users[:num_members]):
            tenant_user, _ = TenantUser.objects.get_or_create(
                tenant=tenant,
                user_id=user.user_id,
                defaults={
                    "status": TenantUserStatus.ACTIVE,
                    "is_owner": i == 0,  # 第一个用户是 Owner
                },
            )
            tenant_users.append(tenant_user)
        
        return tenant_users

    def _create_roles(self, tenant, tenant_users):
        """为租户创建角色"""
        if not tenant_users:
            return []
        
        owner = tenant_users[0]
        roles = []
        
        role_configs = [
            {
                "code": "admin",
                "name": "管理员",
                "description": "租户管理员，拥有所有权限",
                "is_builtin": True,
            },
            {
                "code": "developer",
                "name": "开发者",
                "description": "可以创建和编辑流程、数据集等",
                "is_builtin": True,
            },
            {
                "code": "analyst",
                "name": "分析师",
                "description": "可以查看数据和报表",
                "is_builtin": True,
            },
            {
                "code": "viewer",
                "name": "访客",
                "description": "只能查看授权的资源",
                "is_builtin": True,
            },
        ]
        
        for config in role_configs:
            role, _ = Role.objects.get_or_create(
                tenant=tenant,
                code=config["code"],
                defaults={
                    "name": config["name"],
                    "description": config["description"],
                    "is_builtin": config["is_builtin"],
                    "status": RoleStatus.ACTIVE,
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
            roles.append(role)
        
        return roles

    def _assign_roles(self, tenant, tenant_users, roles):
        """为租户成员分配角色"""
        if not tenant_users or not roles:
            return
        
        owner = tenant_users[0]
        admin_role = next((r for r in roles if r.code == "admin"), None)
        developer_role = next((r for r in roles if r.code == "developer"), None)
        analyst_role = next((r for r in roles if r.code == "analyst"), None)
        viewer_role = next((r for r in roles if r.code == "viewer"), None)
        
        # Owner 分配管理员角色
        if admin_role:
            TenantUserRole.objects.get_or_create(
                tenant=tenant,
                tenant_user=owner,
                role=admin_role,
                defaults={"created_by": owner},
            )
        
        # 其他成员分配不同角色
        for i, tenant_user in enumerate(tenant_users[1:], start=1):
            if i % 3 == 1 and developer_role:
                role = developer_role
            elif i % 3 == 2 and analyst_role:
                role = analyst_role
            elif viewer_role:
                role = viewer_role
            else:
                continue
            
            TenantUserRole.objects.get_or_create(
                tenant=tenant,
                tenant_user=tenant_user,
                role=role,
                defaults={"created_by": owner},
            )

    def _create_resource_tree(self, tenant, owner):
        """为租户创建资源树"""
        nodes = []
        
        # 确保根节点存在
        root_nodes = ResourceTreeNode.ensure_root_nodes_for_tenant(tenant)
        nodes.extend(root_nodes)
        
        # 为每个 scope 创建一些文件夹和资源
        for scope in ResourceScope.values:
            root = next((n for n in root_nodes if n.scope == scope), None)
            if not root:
                continue
            
            # 创建文件夹
            folder_names = ["生产环境", "测试环境", "开发环境"]
            for i, folder_name in enumerate(folder_names):
                folder, _ = ResourceTreeNode.objects.get_or_create(
                    tenant=tenant,
                    scope=scope,
                    parent_node=root,
                    node_type=ResourceNodeType.FOLDER,
                    name=folder_name,
                    defaults={
                        "sort_order": i,
                        "path": f"/{root.node_id}/{folder_name}/",
                        "depth": 1,
                        "created_by": owner,
                        "updated_by": owner,
                    },
                )
                nodes.append(folder)
                
                # 在文件夹下创建一些资源
                for j in range(1, 4):
                    resource_name = f"{self._get_scope_resource_name(scope)}{j}"
                    resource, _ = ResourceTreeNode.objects.get_or_create(
                        tenant=tenant,
                        scope=scope,
                        parent_node=folder,
                        node_type=ResourceNodeType.RESOURCE,
                        name=resource_name,
                        defaults={
                            "ref_type": scope,
                            "ref_resource_id": 1000 + j,  # 模拟资源ID
                            "sort_order": j - 1,
                            "path": f"/{root.node_id}/{folder.node_id}/{resource_name}/",
                            "depth": 2,
                            "created_by": owner,
                            "updated_by": owner,
                        },
                    )
                    nodes.append(resource)
        
        return nodes

    def _get_scope_resource_name(self, scope):
        """根据资源域返回资源名称前缀"""
        scope_names = {
            ResourceScope.TABLE: "用户表",
            ResourceScope.FLOW: "数据处理流程",
            ResourceScope.DATASET: "销售数据集",
            ResourceScope.DASHBOARD: "业务看板",
        }
        return scope_names.get(scope, "资源")

    def _assign_permissions(self, tenant, roles, nodes, owner):
        """为角色分配资源权限"""
        if not roles or not nodes:
            return
        
        admin_role = next((r for r in roles if r.code == "admin"), None)
        developer_role = next((r for r in roles if r.code == "developer"), None)
        analyst_role = next((r for r in roles if r.code == "analyst"), None)
        viewer_role = next((r for r in roles if r.code == "viewer"), None)
        
        # 找出所有根节点
        root_nodes = [n for n in nodes if n.parent_node is None]
        
        # 管理员：对所有根节点有 MANAGE 权限
        if admin_role:
            for root in root_nodes:
                for resource_type in ResourceType.values:
                    RolePermission.objects.get_or_create(
                        tenant=tenant,
                        role=admin_role,
                        resource_type=resource_type,
                        resource_tree_node=root,
                        defaults={
                            "permission": PermissionLevel.MANAGE,
                            "created_by": owner,
                            "updated_by": owner,
                        },
                    )
        
        # 开发者：对部分资源有 EDIT 权限
        if developer_role:
            for root in root_nodes:
                if root.scope in [ResourceScope.FLOW, ResourceScope.DATASET]:
                    for resource_type in [ResourceType.FLOW, ResourceType.DATASET]:
                        RolePermission.objects.get_or_create(
                            tenant=tenant,
                            role=developer_role,
                            resource_type=resource_type,
                            resource_tree_node=root,
                            defaults={
                                "permission": PermissionLevel.EDIT,
                                "created_by": owner,
                                "updated_by": owner,
                            },
                        )
        
        # 分析师：对所有资源有 VIEW 权限
        if analyst_role:
            for root in root_nodes:
                for resource_type in ResourceType.values:
                    RolePermission.objects.get_or_create(
                        tenant=tenant,
                        role=analyst_role,
                        resource_type=resource_type,
                        resource_tree_node=root,
                        defaults={
                            "permission": PermissionLevel.VIEW,
                            "created_by": owner,
                            "updated_by": owner,
                        },
                    )
        
        # 访客：只对特定文件夹有 VIEW 权限
        if viewer_role:
            test_folders = [
                n for n in nodes 
                if n.node_type == ResourceNodeType.FOLDER and "测试" in n.name
            ]
            for folder in test_folders:
                RolePermission.objects.get_or_create(
                    tenant=tenant,
                    role=viewer_role,
                    resource_type=ResourceType.DATASET,
                    resource_tree_node=folder,
                    defaults={
                        "permission": PermissionLevel.VIEW,
                        "created_by": owner,
                        "updated_by": owner,
                    },
                )
