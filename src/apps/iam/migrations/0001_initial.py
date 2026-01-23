"""
IAM initial models.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("role_id", models.BigAutoField(help_text="角色ID", primary_key=True, serialize=False)),
                ("code", models.CharField(help_text="角色编码（租户内唯一）", max_length=64)),
                ("name", models.CharField(help_text="角色名称", max_length=64)),
                ("description", models.CharField(blank=True, help_text="角色说明", max_length=255, null=True)),
                ("is_builtin", models.BooleanField(default=False, help_text="是否系统内置")),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "活跃"), ("DISABLED", "已禁用")],
                        default="ACTIVE",
                        help_text="角色状态：ACTIVE=活跃，DISABLED=已禁用",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        db_column="created_by",
                        help_text="创建人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_roles",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        db_column="updated_by",
                        help_text="更新人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_roles",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        help_text="租户",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roles",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "role",
                "indexes": [
                    models.Index(fields=["tenant", "code"], name="uk_role_code"),
                    models.Index(fields=["tenant", "status"], name="idx_role_status"),
                ],
                "unique_together": {("tenant", "code")},
            },
        ),
        migrations.CreateModel(
            name="TenantUserRole",
            fields=[
                ("tenant_user_role_id", models.BigAutoField(help_text="记录ID", primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        db_column="created_by",
                        help_text="操作人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_role_bindings",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        help_text="角色",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_bindings",
                        to="iam.role",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        help_text="租户",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tenant_user_roles",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "tenant_user",
                    models.ForeignKey(
                        db_column="tenant_user_id",
                        help_text="租户成员",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_bindings",
                        to="tenants.tenantuser",
                    ),
                ),
            ],
            options={
                "db_table": "tenant_user_role",
                "indexes": [
                    models.Index(fields=["tenant", "tenant_user", "role"], name="uk_user_role"),
                    models.Index(fields=["tenant", "role"], name="idx_role_users"),
                ],
                "unique_together": {("tenant", "tenant_user", "role")},
            },
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("role_permission_id", models.BigAutoField(help_text="记录ID", primary_key=True, serialize=False)),
                (
                    "resource_type",
                    models.CharField(
                        choices=[
                            ("TABLE_SCHEMA", "表结构"),
                            ("TABLE_DATA", "表数据"),
                            ("FLOW", "流程"),
                            ("DATASET", "数据集"),
                            ("DASHBOARD", "看板"),
                        ],
                        help_text="资源类型",
                        max_length=32,
                    ),
                ),
                (
                    "resource_tree_node_id",
                    models.BigIntegerField(
                        help_text="资源树节点ID（FK → resource_tree_node.node_id）"
                    ),
                ),
                (
                    "permission",
                    models.CharField(
                        choices=[
                            ("NONE", "无权限"),
                            ("VIEW", "可查看"),
                            ("EDIT", "可编辑"),
                            ("MANAGE", "可管理"),
                        ],
                        default="NONE",
                        help_text="权限等级",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        db_column="created_by",
                        help_text="创建人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_role_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        db_column="updated_by",
                        help_text="更新人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_role_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        help_text="角色",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resource_permissions",
                        to="iam.role",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        help_text="租户",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "role_permission",
                "indexes": [
                    models.Index(
                        fields=["tenant", "role", "resource_type", "resource_tree_node_id"],
                        name="uk_role_perm",
                    ),
                    models.Index(fields=["tenant", "resource_tree_node_id"], name="idx_perm_node"),
                    models.Index(fields=["tenant", "role"], name="idx_perm_role"),
                ],
                "unique_together": {("tenant", "role", "resource_type", "resource_tree_node_id")},
            },
        ),
        migrations.CreateModel(
            name="RowPermission",
            fields=[
                ("row_permission_id", models.BigAutoField(help_text="规则ID", primary_key=True, serialize=False)),
                (
                    "table_id",
                    models.BigIntegerField(help_text="表ID（FK → modeling_table.table_id）"),
                ),
                ("name", models.CharField(blank=True, help_text="规则名称", max_length=64, null=True)),
                ("filter_dsl", models.JSONField(help_text="行过滤 DSL（FilterDSL）")),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "活跃"), ("DISABLED", "已禁用")],
                        default="ACTIVE",
                        help_text="规则状态",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        db_column="created_by",
                        help_text="创建人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_row_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        db_column="updated_by",
                        help_text="更新人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_row_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        help_text="角色",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="row_permissions",
                        to="iam.role",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        help_text="租户",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="row_permissions",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "row_permission",
                "indexes": [
                    models.Index(fields=["tenant", "role", "table_id"], name="uk_rowperm"),
                    models.Index(fields=["tenant", "table_id"], name="idx_rowperm_table"),
                ],
                "unique_together": {("tenant", "role", "table_id")},
            },
        ),
        migrations.CreateModel(
            name="ColumnPermission",
            fields=[
                (
                    "column_permission_id",
                    models.BigAutoField(help_text="记录ID", primary_key=True, serialize=False),
                ),
                (
                    "table_id",
                    models.BigIntegerField(help_text="表ID（FK → modeling_table.table_id）"),
                ),
                (
                    "field_id",
                    models.BigIntegerField(help_text="字段ID（FK → modeling_field.field_id）"),
                ),
                (
                    "access_level",
                    models.CharField(
                        choices=[("HIDDEN", "不可见"), ("READONLY", "只读"), ("READWRITE", "可写")],
                        default="READWRITE",
                        help_text="列权限",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        db_column="created_by",
                        help_text="创建人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_column_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        db_column="updated_by",
                        help_text="更新人（tenant_user_id）",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_column_permissions",
                        to="tenants.tenantuser",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        db_column="role_id",
                        help_text="角色",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="column_permissions",
                        to="iam.role",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        help_text="租户",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="column_permissions",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "column_permission",
                "indexes": [
                    models.Index(
                        fields=["tenant", "role", "table_id", "field_id"],
                        name="uk_colperm",
                    ),
                    models.Index(
                        fields=["tenant", "role", "table_id"],
                        name="idx_colperm_role_table",
                    ),
                ],
                "unique_together": {("tenant", "role", "table_id", "field_id")},
            },
        ),
    ]

