"""
IAM API URLs

T3.2: 角色管理
"""
from django.urls import path

from apps.iam.api.views_roles import RoleDetailView, RoleListCreateView

app_name = "iam"

urlpatterns = [
    path("roles", RoleListCreateView.as_view(), name="role-list"),
    path("roles/<int:role_id>", RoleDetailView.as_view(), name="role-detail"),
]
