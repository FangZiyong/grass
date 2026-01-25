from django.contrib import admin

from apps.resource_tree.models.resource_node import ResourceTreeNode


@admin.register(ResourceTreeNode)
class ResourceTreeNodeAdmin(admin.ModelAdmin):
    list_display = (
        "node_id",
        "tenant_name",
        "scope",
        "node_type",
        "name",
        "parent_node_id",
        "depth",
        "sort_order",
        "is_deleted",
    )
    search_fields = ("name", "tenant__name", "tenant__code")
    list_filter = ("scope", "node_type", "is_deleted")
    ordering = ("-node_id",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("tenant", "parent_node", "created_by", "updated_by")
    raw_id_fields = ("parent_node", "created_by", "updated_by")

    def tenant_name(self, obj):
        return obj.tenant.name

    tenant_name.short_description = "tenant name"
    tenant_name.admin_order_field = "tenant__name"
