from django.contrib import admin

from apps.tenants.models.tenant import Tenant
from apps.tenants.models.tenant_user import TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("tenant_id", "code", "name", "status", "plan")
    search_fields = ("code", "name")
    list_filter = ("status", "plan")
    ordering = ("-tenant_id",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = (
        "tenant_user_id",
        "tenant_id",
        "user_id",
        "status",
        "is_owner",
        "last_login",
    )
    search_fields = ("tenant__code", "tenant__name", "user_id")
    list_filter = ("status", "is_owner")
    ordering = ("-tenant_user_id",)
    readonly_fields = ("created_at", "updated_at")
