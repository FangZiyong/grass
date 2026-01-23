from django.contrib import admin

from apps.iam.models.column_perms import ColumnPermission
from apps.iam.models.grants import RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role
from apps.iam.models.row_perms import RowPermission


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("role_id", "tenant_id", "code", "name", "status", "is_builtin")
    search_fields = ("code", "name")
    list_filter = ("status", "is_builtin")
    ordering = ("-role_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(TenantUserRole)
class TenantUserRoleAdmin(admin.ModelAdmin):
    list_display = ("tenant_user_role_id", "tenant_id", "tenant_user_id", "role_id", "created_at")
    search_fields = ("tenant_id", "tenant_user_id", "role_id")
    ordering = ("-tenant_user_role_id",)
    readonly_fields = ("created_at",)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = (
        "role_permission_id",
        "tenant_id",
        "role_id",
        "resource_type",
        "resource_tree_node_id",
        "permission",
    )
    search_fields = ("tenant_id", "role_id", "resource_tree_node_id")
    list_filter = ("resource_type", "permission")
    ordering = ("-role_permission_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(RowPermission)
class RowPermissionAdmin(admin.ModelAdmin):
    list_display = ("row_permission_id", "tenant_id", "role_id", "table_id", "status")
    search_fields = ("tenant_id", "role_id", "table_id")
    list_filter = ("status",)
    ordering = ("-row_permission_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ColumnPermission)
class ColumnPermissionAdmin(admin.ModelAdmin):
    list_display = ("column_permission_id", "tenant_id", "role_id", "table_id", "field_id", "access_level")
    search_fields = ("tenant_id", "role_id", "table_id", "field_id")
    list_filter = ("access_level",)
    ordering = ("-column_permission_id",)
    readonly_fields = ("created_at", "updated_at")

