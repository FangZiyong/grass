"""
Tenant API URLs

根据 architecture.md 和 tech.md：
- GET /api/tenants：租户列表（T2.2任务）
- POST /api/tenants/switch：切换租户（T2.3任务）
"""
from django.urls import path

from apps.tenants.api.views_tenants import tenant_list_view, tenant_switch_view

app_name = "tenants"

urlpatterns = [
    path("tenants", tenant_list_view, name="tenant-list"),
    path("tenants/switch", tenant_switch_view, name="tenant-switch"),
]

