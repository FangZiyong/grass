from django.contrib import admin

from apps.accounts.models.users import GlobalUser
from apps.iam.models.column_perms import ColumnPermission
from apps.iam.models.grants import RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.iam.models.roles import Role
from apps.iam.models.row_perms import RowPermission


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("role_id", "tenant_name", "code", "name", "status", "is_builtin")
    search_fields = ("code", "name")
    list_filter = ("status", "is_builtin")
    ordering = ("-role_id",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("tenant",)

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"


@admin.register(TenantUserRole)
class TenantUserRoleAdmin(admin.ModelAdmin):
    list_display = ("tenant_user_role_id", "tenant_name", "tenant_user_name", "role_name", "created_at")
    search_fields = ("tenant_id", "tenant_user_id", "role_id")
    ordering = ("-tenant_user_role_id",)
    readonly_fields = ("created_at",)
    list_select_related = ("tenant", "tenant_user", "role")

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"

    def tenant_user_name(self, obj):
        user_id = obj.tenant_user.user_id
        if user_id is None:
            return "-"
        cache = getattr(self, "_global_user_cache", None)
        if cache is None:
            cache = {}
            self._global_user_cache = cache
        if user_id in cache:
            return cache[user_id]
        user = GlobalUser.objects.filter(user_id=user_id).only("display_name").first()
        name = user.display_name if user else "-"
        cache[user_id] = name
        return name

    tenant_user_name.short_description = "user name"

    def role_name(self, obj):
        return obj.role.name

    role_name.short_description = "role name"
    role_name.admin_order_field = "role__name"


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = (
        "role_permission_id",
        "tenant_name",
        "role_name",
        "resource_type",
        "resource_tree_node_id",
        "permission",
    )
    search_fields = ("tenant_id", "role_id", "resource_tree_node_id")
    list_filter = ("resource_type", "permission")
    ordering = ("-role_permission_id",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("tenant", "role")

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"

    def role_name(self, obj):
        return obj.role.name

    role_name.short_description = "role name"
    role_name.admin_order_field = "role__name"


@admin.register(RowPermission)
class RowPermissionAdmin(admin.ModelAdmin):
    list_display = ("row_permission_id", "tenant_name", "role_name", "table_id", "status")
    search_fields = ("tenant_id", "role_id", "table_id")
    list_filter = ("status",)
    ordering = ("-row_permission_id",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("tenant", "role")

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"

    def role_name(self, obj):
        return obj.role.name

    role_name.short_description = "role name"
    role_name.admin_order_field = "role__name"


@admin.register(ColumnPermission)
class ColumnPermissionAdmin(admin.ModelAdmin):
    list_display = ("column_permission_id", "tenant_name", "role_name", "table_id", "field_id", "access_level")
    search_fields = ("tenant_id", "role_id", "table_id", "field_id")
    list_filter = ("access_level",)
    ordering = ("-column_permission_id",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("tenant", "role")

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"

    def role_name(self, obj):
        return obj.role.name

    role_name.short_description = "role name"
    role_name.admin_order_field = "role__name"

