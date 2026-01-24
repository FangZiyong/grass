"""
IAM API URLs

T3.2: 角色管理
"""
from django.urls import path

from apps.iam.api.views_membership import (
    MemberOwnerView,
    MemberRoleBindView,
    MemberRoleUnbindView,
    RoleUsersListView,
)
from apps.iam.api.views_permissions import (
    ResourcePermissionPanelView,
    RoleResourcePermissionsView,
)
from apps.iam.api.views_roles import RoleDetailView, RoleListCreateView

app_name = "iam"

urlpatterns = [
    path("roles", RoleListCreateView.as_view(), name="role-list"),
    path("roles/<int:role_id>", RoleDetailView.as_view(), name="role-detail"),
    path(
        "roles/<int:role_id>/users",
        RoleUsersListView.as_view(),
        name="role-users-list",
    ),
    path(
        "roles/<int:role_id>/resource-permissions",
        RoleResourcePermissionsView.as_view(),
        name="role-resource-permissions",
    ),
    path(
        "permissions/resources/<int:resource_node_id>",
        ResourcePermissionPanelView.as_view(),
        name="permission-panel",
    ),
    path(
        "users/<int:tenant_user_id>/roles",
        MemberRoleBindView.as_view(),
        name="member-role-bind",
    ),
    path(
        "users/<int:tenant_user_id>/roles/<int:role_id>",
        MemberRoleUnbindView.as_view(),
        name="member-role-unbind",
    ),
    path(
        "users/<int:tenant_user_id>/owner",
        MemberOwnerView.as_view(),
        name="member-owner",
    ),
]
