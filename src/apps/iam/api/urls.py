"""
IAM API URLs

路由清单：
- 角色管理
  - GET/POST /api/roles - 角色列表/创建
  - GET/PATCH/DELETE /api/roles/{role_id} - 角色详情/更新/删除
  - GET /api/roles/{role_id}/users - 角色成员列表

- 成员角色绑定
  - POST /api/users/{tenant_user_id}/roles - 绑定角色
  - DELETE /api/users/{tenant_user_id}/roles/{role_id} - 解绑角色

- Owner 设定
  - POST/DELETE /api/users/{tenant_user_id}/owner - 设为/取消 Owner

- 角色资源授权
  - GET/PUT /api/roles/{role_id}/resource-permissions - 查询/保存角色资源授权

- 权限面板
  - GET /api/permissions/resources/{resource_node_id} - 权限面板数据

- 授权管理
  - POST /api/permissions/grants - 创建/更新授权
  - DELETE /api/permissions/grants/{grant_id} - 撤销授权
"""
from django.urls import path

from apps.iam.api.views_membership import (
    MemberOwnerView,
    MemberRoleBindView,
    MemberRoleUnbindView,
    RoleUsersListView,
)
from apps.iam.api.views_permissions import (
    GrantDetailView,
    GrantsView,
    ResourcePermissionPanelView,
    RoleResourcePermissionsView,
)
from apps.iam.api.views_roles import RoleDetailView, RoleListCreateView

app_name = "iam"

urlpatterns = [
    # ======== 角色管理 ========
    path("roles", RoleListCreateView.as_view(), name="role-list"),
    path("roles/<int:role_id>", RoleDetailView.as_view(), name="role-detail"),
    path(
        "roles/<int:role_id>/users",
        RoleUsersListView.as_view(),
        name="role-users-list",
    ),
    # ======== 角色资源授权 ========
    path(
        "roles/<int:role_id>/resource-permissions",
        RoleResourcePermissionsView.as_view(),
        name="role-resource-permissions",
    ),
    # ======== 权限面板 ========
    path(
        "permissions/resources/<int:resource_node_id>",
        ResourcePermissionPanelView.as_view(),
        name="permission-panel",
    ),
    # ======== 授权管理 ========
    path(
        "permissions/grants",
        GrantsView.as_view(),
        name="grants",
    ),
    path(
        "permissions/grants/<int:grant_id>",
        GrantDetailView.as_view(),
        name="grant-detail",
    ),
    # ======== 成员角色绑定 ========
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
    # ======== Owner 设定 ========
    path(
        "users/<int:tenant_user_id>/owner",
        MemberOwnerView.as_view(),
        name="member-owner",
    ),
]
