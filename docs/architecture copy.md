# Django 后端目录设计（与 PRD/技术文档对齐，V1.2）

- 生成日期：2025-12-23
- 变更：补齐 platform_admin 接口组、补齐 platform 审计 meta 接口；修正 platform_admin 目录说明；新增 Endpoint→ 代码落点映射表（便于编程模型按图索骥）。

---

## 0. 目标与约束

本文件用于**指导后端代码实现**：目录结构、文件职责、模型归属、服务划分、以及接口清单与代码落点。所有接口清单以 `tech.md` 为准（文档里标注“必须实现”的均视为硬要求）。

**硬约束（实现必须满足）**

- `src/` 布局；`config/` 只放项目配置；业务逻辑只放在 `apps/`；横切能力下沉到 `common/`。
- 业务写操作必须走 `services/*`（用例层），只读查询走 `selectors.py`（Query 层），避免 View 直接写数据库。
- 权限校验：资源级（RolePermission）+ 行级（RowPermission）+ 列级（ColumnPermission）都必须在后端强制执行。
- 审计：权限变更、关键配置变更（Flow/Modeling/Reports）必须写审计（见 `common.audit.emitter`）。
- 平台后台：所有 `/admin/*` 与 `/admin/api/*` 必须只允许 `is_platform_admin=true` 用户访问，否则 403。

---

## 1. 总体目录树（ASCII Tree）

```text
repo/
├── pyproject.toml
├── README.md
├── compose.yml
├── .env.example
├── docker/
│   ├── web.Dockerfile
│   ├── worker.Dockerfile
│   └── scheduler.Dockerfile
├── scripts/
│   ├── manage.sh
│   ├── lint.sh
│   └── test.sh
└── src/
    ├── manage.py
    ├── config/
    │   ├── __init__.py
    │   ├── asgi.py
    │   ├── wsgi.py
    │   ├── urls.py
    │   ├── celery.py
    │   ├── logging.py
    │   └── settings/
    │       ├── __init__.py
    │       ├── base.py
    │       ├── local.py
    │       ├── test.py
    │       └── prod.py
    ├── common/
    │   ├── __init__.py
    │   ├── constants.py
    │   ├── types.py
    │   ├── http/
    │   │   ├── __init__.py
    │   │   ├── response.py
    │   │   └── pagination.py
    │   ├── errors/
    │   │   ├── __init__.py
    │   │   ├── codes.py
    │   │   ├── exceptions.py
    │   │   └── handlers.py
    │   ├── middleware/
    │   │   ├── __init__.py
    │   │   ├── request_id.py
    │   │   ├── tenant_context.py
    │   │   └── auth_context.py
    │   ├── dsl/
    │   │   ├── __init__.py
    │   │   ├── filter_schema.py
    │   │   ├── validator.py
    │   │   └── compiler/
    │   │       ├── __init__.py
    │   │       ├── ast.py
    │   │       └── sql.py
    │   ├── audit/
    │   │   ├── __init__.py
    │   │   ├── emitter.py
    │   │   └── diff.py
    │   └── utils/
    │       ├── __init__.py
    │       ├── time.py
    │       └── ids.py
    ├── integrations/
    │   ├── __init__.py
    │   ├── dw/
    │   │   ├── __init__.py
    │   │   ├── client.py
    │   │   ├── ddl.py
    │   │   └── swap.py
    │   └── storage/
    │       ├── __init__.py
    │       └── client.py
    ├── api/
    │   ├── __init__.py
    │   └── v1/
    │       ├── __init__.py
    │       ├── urls.py
    │       └── schema.py
    ├── apps/
    │   ├── accounts/
    │   ├── tenants/
    │   ├── iam/
    │   ├── resource_tree/
    │   ├── modeling/
    │   ├── query_engine/
    │   ├── execution/
    │   ├── reports/
    │   ├── flows/
    │   ├── notifications/
    │   ├── audit_logs/
    │   ├── platform_admin/
    │   └── assist/
    └── tests/
        ├── __init__.py
        └── test_smoke.py
```

---

## 2. 分层与依赖方向（防循环依赖）

- `config/`：Django 项目配置（settings/urls/asgi/wsgi/celery/logging）。
- `common/`：跨领域基础能力（TenantContext、统一错误码、FilterDSL 编译、审计 emitter 等）。
- `integrations/`：外部系统适配（DW、存储、LLM）。
- `apps/*`：按业务域拆分（accounts/tenants/iam/modeling/flows/reports/…）。

**依赖规则（必须遵守）**

1. `apps/*` 可以依赖 `common/` 与 `integrations/`。
2. `apps/A` 与 `apps/B` 互相调用时：优先通过 `selectors.py`（只读）或 service 的“稳定接口”函数；禁止直接 import 对方 models 进行复杂操作。
3. `execution/` 不反向依赖 `reports/flows/modeling`：通过 `execution.registry.tasks` 做 handler 注册反转依赖。

---

## 3. apps 清单（与 tech.md 模块映射）

- `accounts`：平台用户与会话（GlobalUser/AuthSession）；`/api/auth/*`、`/api/me`
- `tenants`：租户（Tenant）与成员实体（TenantUser）；`/api/tenants`、`/api/tenants/switch`
- `iam`：租户内角色与权限（Role/RolePermission/RowPermission/ColumnPermission）；接口挂在 `/api/tenants/{tenant_id}/...`
- `resource_tree`：资源树（ResourceTreeNode），对接 TABLE/FLOW/DATASET/DASHBOARD 等 scope
- `modeling`：建模（ModelingTable/ModelingField + 记录 CRUD + REFERENCE 推导关系）
- `query_engine`：Query/Filter 编译与执行；`/api/query/*`
- `execution`：统一执行框架（TaskRunInstance + scheduler/worker）
- `reports`：报表链路（Dataset/Chart/Dashboard/ExportJob/DatasetRefreshRun）
- `flows`：Flow DAG 与运行（Flow/Node/Edge/Run/NodeRun/RunLog）
- `notifications`：站内通知；`/api/notifications*`
- `audit_logs`：租户审计；`/api/audit-logs*`
- `platform_admin`：平台后台（`/admin/api/*`）+ 平台审计（`/api/platform/audit-logs*`）
- `assist`：LLM 辅助；`/api/assist/code-suggest`

---

# accounts ｜账号与认证

**模块定位**：平台用户、登录会话、token 签发与校验；对外提供 `/api/auth/*` 与 `/api/me`。

## 目录结构

```text
src/apps/accounts/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── users.py              # GlobalUser（global_user）
│   └── sessions.py           # AuthSession（auth_session）
├── selectors.py
├── services/
│   ├── __init__.py
│   ├── auth.py
│   └── tokens.py
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── views_auth.py
│   ├── views_me.py
│   └── urls.py
├── migrations/
└── tests/
    ├── __init__.py
    ├── test_auth.py
    └── test_me.py
```

## 模型（与 tech.md 数据表对齐）

| 文件                 | 模型          | db_table       | 说明                                                                                        |
| -------------------- | ------------- | -------------- | ------------------------------------------------------------------------------------------- |
| `models/users.py`    | `GlobalUser`  | `global_user`  | 平台账号；字段含 `email/username/password_hash/is_platform_admin/status/last_login_at` 等。 |
| `models/sessions.py` | `AuthSession` | `auth_session` | 登录会话；保存 refresh token hash、过期时间、状态、UA/IP 等 meta。                          |

## Services（用例层：写操作）

- `services/auth.py`
  - `login()`：校验凭证、写 `auth_session`、更新 `global_user.last_login_at`、下发 refresh cookie
  - `logout()`：撤销当前 session
  - `refresh()`：校验 refresh 会话，签发新的 access
- `services/tokens.py`
  - `issue_access_token()` / `verify_access_token()`
  - `hash_refresh_token()` / `verify_refresh_session()`

## API（接口清单与代码落点）

| 方法 | 路径                | 说明                                           | View（views\_\*.py）     | Serializer          | Service（函数）                     | 权限           |
| ---- | ------------------- | ---------------------------------------------- | ------------------------ | ------------------- | ----------------------------------- | -------------- |
| POST | `/api/auth/login`   | 登录（创建 auth_session，下发 refresh cookie） | `views_auth.LoginView`   | `LoginSerializer`   | `auth_service.login()`              | 公开（带限流） |
| POST | `/api/auth/logout`  | 退出（撤销当前会话）                           | `views_auth.LogoutView`  | `LogoutSerializer`  | `auth_service.logout()`             | 登录态         |
| POST | `/api/auth/refresh` | 刷新 access token（校验 refresh 会话）         | `views_auth.RefreshView` | `RefreshSerializer` | `auth_service.refresh()`            | refresh cookie |
| GET  | `/api/me`           | 获取当前用户信息（含 tenant_user/role 概览）   | `views_me.MeView`        | `MeSerializer`      | `account_selector.get_me_payload()` | 登录态         |

---

# tenants ｜租户切换

**模块定位**：租户元信息与“当前会话租户上下文”切换（成员/角色写操作见 iam/platform_admin）。

## 目录结构

```text
src/apps/tenants/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── tenant.py             # Tenant（tenant）
│   └── tenant_user.py        # TenantUser（tenant_user）
├── selectors.py
├── services.py               # switch_tenant、成员只读视图等（写操作主要在 iam / platform_admin）
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views_tenants.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                    | 模型         | db_table      | 说明                                                                                      |
| ----------------------- | ------------ | ------------- | ----------------------------------------------------------------------------------------- |
| `models/tenant.py`      | `Tenant`     | `tenant`      | 租户元信息：`code/name/plan/status/timezone`；`status=SUSPENDED` 时需停止 Flow 调度触发。 |
| `models/tenant_user.py` | `TenantUser` | `tenant_user` | 用户在租户内的身份：`tenant_id/global_user_id/display_name/status/is_owner` 等。          |

## Services（用例层：写操作）

- `services.py`
  - `switch_tenant()`：切换当前会话租户上下文（TenantContext）
- 写操作（成员/角色/权限）主要在：`iam/services/*`（租户内）与 `platform_admin/services/*`（平台视角）。

## API（接口清单与代码落点）

| 方法 | 路径                  | 说明                                   | View（views\_\*.py）             | Serializer               | Service（函数）                     | 权限   |
| ---- | --------------------- | -------------------------------------- | -------------------------------- | ------------------------ | ----------------------------------- | ------ |
| GET  | `/api/tenants`        | 获取可切换租户列表（当前用户所属租户） | `views_tenants.TenantListView`   | `TenantBriefSerializer`  | `tenant_selector.list_my_tenants()` | 登录态 |
| POST | `/api/tenants/switch` | 切换当前租户（写入会话/上下文）        | `views_tenants.TenantSwitchView` | `TenantSwitchSerializer` | `tenant_service.switch_tenant()`    | 登录态 |

---

# iam ｜租户内角色与权限

**模块定位**：租户内 RBAC（资源/行/列权限）+ Owner 规则；接口挂载在 `/api/tenants/{tenant_id}/...`。

## 目录结构

```text
src/apps/iam/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── role.py               # Role（role）
│   ├── membership.py         # TenantUserRole（tenant_user_role）
│   ├── role_permission.py    # RolePermission（role_permission）
│   ├── row_permission.py     # RowPermission（row_permission）
│   └── column_permission.py  # ColumnPermission（column_permission）
├── engine/
│   ├── __init__.py
│   ├── permission_engine.py
│   ├── rowperm_merge.py
│   └── colperm_merge.py
├── selectors.py
├── services/
│   ├── __init__.py
│   ├── roles.py
│   ├── membership.py
│   └── permissions.py        # resource/row/column perms
├── api/
│   ├── __init__.py
│   ├── serializers_roles.py
│   ├── serializers_permissions.py
│   ├── permissions.py
│   ├── views_roles.py
│   ├── views_membership.py
│   ├── views_permissions.py
│   ├── views_row_perms.py
│   ├── views_column_perms.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                          | 模型               | db_table            | 说明                                    |
| ----------------------------- | ------------------ | ------------------- | --------------------------------------- |
| `models/role.py`              | `Role`             | `role`              | 租户内角色（系统/自定义）。             |
| `models/membership.py`        | `TenantUserRole`   | `tenant_user_role`  | 成员-角色关联。                         |
| `models/role_permission.py`   | `RolePermission`   | `role_permission`   | 资源级权限（scope/object_type/level）。 |
| `models/row_permission.py`    | `RowPermission`    | `row_permission`    | 行权限（`filter_json` 走 FilterDSL）。  |
| `models/column_permission.py` | `ColumnPermission` | `column_permission` | 列权限（隐藏/只读/读写）。              |

## Services（用例层：写操作）

- `services/roles.py`
  - `list_roles()` / `create_role()` / `update_role()` / `delete_role()`
- `services/membership.py`
  - `grant_roles()` / `revoke_role()`
  - `set_owner()` / `unset_owner()`（Owner 转移与校验）
- `services/permissions.py`
  - `get_role_resource_perms()` / `set_role_resource_perms()`
  - `get_column_perms()` / `set_column_perms()`
  - `list_row_perms()` / `create_row_perm()` / `update_row_perm()` / `delete_row_perm()`
- `engine/permission_engine.py`
  - 计算最终资源权限 + 叠加行/列权限（供 QueryEngine 与记录读取复用）

## API（接口清单与代码落点）

| 方法   | 路径                                                                       | 说明                                  | View（views\_\*.py）                             | Serializer                      | Service（函数）                                 | 权限                                 |
| ------ | -------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------ | ------------------------------- | ----------------------------------------------- | ------------------------------------ |
| POST   | `/api/permissions/grants`                                                  | 创建授权 grant（资源级）              | `views_permissions.GrantCreateView`              | `GrantCreateSerializer`         | `permission_service.create_grant()`             | TENANT_SETTINGS:MANAGE               |
| DELETE | `/api/permissions/grants/{grant_id}`                                       | 删除授权 grant                        | `views_permissions.GrantDeleteView`              | `EmptySerializer`               | `permission_service.delete_grant()`             | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/permissions/resources/{resource_node_id}`                            | 获取资源节点的授权详情（含继承/显式） | `views_permissions.ResourcePermGetView`          | `ResourcePermSerializer`        | `permission_service.get_resource_permissions()` | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/tenants/{tenant_id}/roles`                                           | 角色列表                              | `views_roles.RoleListView`                       | `RoleSerializer`                | `role_service.list_roles()`                     | TENANT_SETTINGS:VIEW/EDIT            |
| POST   | `/api/tenants/{tenant_id}/roles`                                           | 创建角色                              | `views_roles.RoleCreateView`                     | `RoleCreateSerializer`          | `role_service.create_role()`                    | TENANT_SETTINGS:MANAGE               |
| DELETE | `/api/tenants/{tenant_id}/roles/{role_id}`                                 | 删除角色（需校验无绑定或策略）        | `views_roles.RoleDeleteView`                     | `EmptySerializer`               | `role_service.delete_role()`                    | TENANT_SETTINGS:MANAGE               |
| PATCH  | `/api/tenants/{tenant_id}/roles/{role_id}`                                 | 编辑角色（名称/描述等）               | `views_roles.RoleUpdateView`                     | `RoleUpdateSerializer`          | `role_service.update_role()`                    | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/tenants/{tenant_id}/roles/{role_id}/resource-permissions`            | 读取角色资源权限（按 scope）          | `views_role_permissions.RoleResourcePermGetView` | `RoleResourcePermSerializer`    | `permission_service.get_role_resource_perms()`  | TENANT_SETTINGS:MANAGE               |
| PUT    | `/api/tenants/{tenant_id}/roles/{role_id}/resource-permissions`            | 覆盖更新角色资源权限（按 scope）      | `views_role_permissions.RoleResourcePermPutView` | `RoleResourcePermPutSerializer` | `permission_service.set_role_resource_perms()`  | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/tenants/{tenant_id}/tables/{table_id}/column-permissions`            | 读取列权限（role_id 维度）            | `views_column_perms.ColumnPermGetView`           | `ColumnPermSerializer`          | `permission_service.get_column_perms()`         | TABLE:MANAGE                         |
| PUT    | `/api/tenants/{tenant_id}/tables/{table_id}/column-permissions`            | 覆盖更新列权限（role_id 维度）        | `views_column_perms.ColumnPermPutView`           | `ColumnPermPutSerializer`       | `permission_service.set_column_perms()`         | TABLE:MANAGE                         |
| GET    | `/api/tenants/{tenant_id}/tables/{table_id}/row-permissions`               | 读取行权限（role_id 维度）            | `views_row_perms.RowPermListView`                | `RowPermSerializer`             | `permission_service.list_row_perms()`           | TABLE:MANAGE                         |
| POST   | `/api/tenants/{tenant_id}/tables/{table_id}/row-permissions`               | 创建行权限（FilterDSL）               | `views_row_perms.RowPermCreateView`              | `RowPermCreateSerializer`       | `permission_service.create_row_perm()`          | TABLE:MANAGE                         |
| DELETE | `/api/tenants/{tenant_id}/tables/{table_id}/row-permissions/{row_perm_id}` | 删除行权限                            | `views_row_perms.RowPermDeleteView`              | `EmptySerializer`               | `permission_service.delete_row_perm()`          | TABLE:MANAGE                         |
| PATCH  | `/api/tenants/{tenant_id}/tables/{table_id}/row-permissions/{row_perm_id}` | 编辑行权限                            | `views_row_perms.RowPermUpdateView`              | `RowPermUpdateSerializer`       | `permission_service.update_row_perm()`          | TABLE:MANAGE                         |
| DELETE | `/api/tenants/{tenant_id}/users/{tenant_user_id}/owner`                    | 取消 Owner（一般仅用于回滚/限制）     | `views_membership.UnsetOwnerView`                | `EmptySerializer`               | `membership_service.unset_owner()`              | TENANT_SETTINGS:MANAGE（owner-only） |
| POST   | `/api/tenants/{tenant_id}/users/{tenant_user_id}/owner`                    | 设为租户 Owner（转移所有权）          | `views_membership.SetOwnerView`                  | `EmptySerializer`               | `membership_service.set_owner()`                | TENANT_SETTINGS:MANAGE（owner-only） |
| POST   | `/api/tenants/{tenant_id}/users/{tenant_user_id}/roles`                    | 给成员授予角色                        | `views_membership.UserRoleGrantView`             | `UserRoleGrantSerializer`       | `membership_service.grant_roles()`              | TENANT_SETTINGS:MANAGE               |
| DELETE | `/api/tenants/{tenant_id}/users/{tenant_user_id}/roles/{role_id}`          | 撤销成员角色                          | `views_membership.UserRoleRevokeView`            | `EmptySerializer`               | `membership_service.revoke_role()`              | TENANT_SETTINGS:MANAGE               |

---

# resource_tree ｜资源树

**模块定位**：按 scope 组织 Folder/Asset 资源；为 TABLE/FLOW/DATASET/DASHBOARD 提供统一目录。

## 目录结构

```text
src/apps/resource_tree/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   └── node.py               # ResourceTreeNode（resource_tree_node）
├── selectors.py
├── services.py               # create/move/reorder/delete + path cache（可选）
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── views_tree.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件             | 模型               | db_table             | 说明                                                                   |
| ---------------- | ------------------ | -------------------- | ---------------------------------------------------------------------- |
| `models/node.py` | `ResourceTreeNode` | `resource_tree_node` | scope 分树；节点类型 FOLDER/ASSET；维护 parent/排序/路径（可选缓存）。 |

## Services（用例层：写操作）

- `services.py`
  - `list_children(scope, parent_id)`：按 scope 获取子节点（过滤 NONE 权限）
  - `create_folder(scope, parent_id, name)`
  - `update_node(scope, id, name/parent/order)`
  - `move_nodes(scope, moves[])`
  - `reorder(scope, parent_id, ordered_ids[])`
  - `delete_folder(scope, id)`：需校验空文件夹或采用递归删除策略（与产品决策一致）

## API（接口清单与代码落点）

| 方法   | 路径                                        | 说明                                   | View（views\_\*.py）          | Serializer               | Service（函数）                | 权限                    |
| ------ | ------------------------------------------- | -------------------------------------- | ----------------------------- | ------------------------ | ------------------------------ | ----------------------- |
| GET    | `/api/resource-tree`                        | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| POST   | `/api/resource-tree/folders`                | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| DELETE | `/api/resource-tree/nodes/{node_id}`        | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| PATCH  | `/api/resource-tree/nodes/{node_id}`        | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| GET    | `/api/resource-trees/TABLE/children`        | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| POST   | `/api/resource-trees/TABLE/folders`         | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| POST   | `/api/resource-trees/TABLE/move`            | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| DELETE | `/api/resource-trees/TABLE/nodes/{node_id}` | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| PATCH  | `/api/resource-trees/TABLE/nodes/{node_id}` | （见 tech.md 描述）                    | `TBD`                         | `TBD`                    | `TBD`                          | TBD                     |
| GET    | `/api/resource-trees/{scope}/children`      | 获取 scope 下 children（node_id 可选） | `views_tree.ChildrenView`     | `TreeChildrenSerializer` | `tree_service.list_children()` | 资源可见（NONE 不可见） |
| POST   | `/api/resource-trees/{scope}/folders`       | 创建文件夹                             | `views_tree.FolderCreateView` | `FolderCreateSerializer` | `tree_service.create_folder()` | 对应 scope:EDIT         |
| DELETE | `/api/resource-trees/{scope}/folders/{id}`  | 删除文件夹（需空/或递归策略）          | `views_tree.FolderDeleteView` | `EmptySerializer`        | `tree_service.delete_folder()` | 对应 scope:MANAGE       |
| POST   | `/api/resource-trees/{scope}/move`          | 移动节点（跨父节点）                   | `views_tree.MoveView`         | `MoveSerializer`         | `tree_service.move_nodes()`    | 对应 scope:EDIT         |
| PATCH  | `/api/resource-trees/{scope}/nodes/{id}`    | 重命名/移动前置校验用字段更新          | `views_tree.NodeUpdateView`   | `NodeUpdateSerializer`   | `tree_service.update_node()`   | 对应 scope:EDIT         |
| POST   | `/api/resource-trees/{scope}/reorder`       | 同层排序调整                           | `views_tree.ReorderView`      | `ReorderSerializer`      | `tree_service.reorder()`       | 对应 scope:EDIT         |

---

# modeling ｜建模

**模块定位**：模型元数据（表/字段）+ 表数据 CRUD；REFERENCE 字段推导关系。

## 目录结构

```text
src/apps/modeling/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── table.py              # ModelingTable（modeling_table）
│   └── field.py              # ModelingField（modeling_field）
├── domain/
│   ├── __init__.py
│   ├── relation.py           # 由 REFERENCE 字段推导关系（不建 relation 表）
│   └── schema_snapshot.py
├── selectors.py
├── services/
│   ├── __init__.py
│   ├── tables.py
│   ├── fields.py
│   └── records.py            # 记录 CRUD（写 DW；读走 QueryEngine）
├── api/
│   ├── __init__.py
│   ├── serializers_tables.py
│   ├── serializers_fields.py
│   ├── serializers_records.py
│   ├── permissions.py
│   ├── views_tables.py
│   ├── views_fields.py
│   ├── views_records.py
│   ├── views_reference.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件              | 模型            | db_table         | 说明                                                         |
| ----------------- | --------------- | ---------------- | ------------------------------------------------------------ |
| `models/table.py` | `ModelingTable` | `modeling_table` | 表元数据：code/display_name/type/desc/owner 等。             |
| `models/field.py` | `ModelingField` | `modeling_field` | 字段元数据：ui_type/数据类型/是否必填/REFERENCE 关联信息等。 |

## Services（用例层：写操作）

- `services/tables.py`
  - `list_tables()` / `create_table()` / `get_table()` / `update_table()` / `delete_table()`
  - 需要联动：DW DDL（`integrations.dw.ddl`）+ 资源树节点（scope=TABLE）+ 审计
- `services/fields.py`
  - `list_fields()` / `create_field()` / `update_field()` / `delete_field()` / `reorder_fields()`
  - `create_field()` 若 ui_type=REFERENCE：写 ref_table/ref_display_field，并由 `domain/relation.py` 提供关系推导
- `services/records.py`
  - `create_record()` / `get_record()` / `update_record()` / `delete_record()` / `batch_delete()`
  - `query_records()`：调用 QueryEngine（FilterDSL + 排序分页 + 行列权限）

## API（接口清单与代码落点）

| 方法   | 路径                                                       | 说明                                              | View（views\_\*.py）                      | Serializer                      | Service（函数）                              | 权限              |
| ------ | ---------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------- | ------------------------------- | -------------------------------------------- | ----------------- |
| GET    | `/api/modeling/tables`                                     | 表列表                                            | `views_tables.TableListView`              | `TableSerializer`               | `table_service.list_tables()`                | MODEL:VIEW        |
| POST   | `/api/modeling/tables`                                     | 创建表（写 MetaDB + 同步 DW DDL）                 | `views_tables.TableCreateView`            | `TableCreateSerializer`         | `table_service.create_table()`               | MODEL:MANAGE      |
| GET    | `/api/modeling/tables/{ref_table_id}/reference-candidates` | REFERENCE 候选字段/展示字段列表                   | `views_reference.ReferenceCandidatesView` | `ReferenceCandidatesSerializer` | `relation_domain.get_reference_candidates()` | MODEL:VIEW        |
| DELETE | `/api/modeling/tables/{table_id}`                          | 删除表（校验引用/数据集/flow）                    | `views_tables.TableDeleteView`            | `EmptySerializer`               | `table_service.delete_table()`               | MODEL:MANAGE      |
| GET    | `/api/modeling/tables/{table_id}`                          | 表详情                                            | `views_tables.TableDetailView`            | `TableDetailSerializer`         | `table_service.get_table()`                  | MODEL:VIEW        |
| PATCH  | `/api/modeling/tables/{table_id}`                          | 编辑表（名称/描述等）                             | `views_tables.TableUpdateView`            | `TableUpdateSerializer`         | `table_service.update_table()`               | MODEL:MANAGE      |
| POST   | `/api/modeling/tables/{table_id}/data/query`               | 查询表数据（QueryEngine：Filter/Sort/Pagination） | `views_records.RecordQueryView`           | `RecordQuerySerializer`         | `record_service.query_records()`             | TABLE_DATA:VIEW   |
| GET    | `/api/modeling/tables/{table_id}/fields`                   | 字段列表                                          | `views_fields.FieldListView`              | `FieldSerializer`               | `field_service.list_fields()`                | MODEL:VIEW        |
| POST   | `/api/modeling/tables/{table_id}/fields`                   | 创建字段（含 REFERENCE 推导）                     | `views_fields.FieldCreateView`            | `FieldCreateSerializer`         | `field_service.create_field()`               | MODEL:MANAGE      |
| POST   | `/api/modeling/tables/{table_id}/fields/reorder`           | 字段顺序调整                                      | `views_fields.FieldReorderView`           | `FieldReorderSerializer`        | `field_service.reorder_fields()`             | MODEL:MANAGE      |
| DELETE | `/api/modeling/tables/{table_id}/fields/{field_id}`        | 删除字段（校验引用）                              | `views_fields.FieldDeleteView`            | `EmptySerializer`               | `field_service.delete_field()`               | MODEL:MANAGE      |
| PATCH  | `/api/modeling/tables/{table_id}/fields/{field_id}`        | 编辑字段                                          | `views_fields.FieldUpdateView`            | `FieldUpdateSerializer`         | `field_service.update_field()`               | MODEL:MANAGE      |
| POST   | `/api/modeling/tables/{table_id}/records`                  | 新增表数据（写 DW）                               | `views_records.RecordCreateView`          | `RecordWriteSerializer`         | `record_service.create_record()`             | TABLE_DATA:EDIT   |
| POST   | `/api/modeling/tables/{table_id}/records/batch-delete`     | 批量删除表数据                                    | `views_records.RecordBatchDeleteView`     | `RecordBatchDeleteSerializer`   | `record_service.batch_delete()`              | TABLE_DATA:MANAGE |
| DELETE | `/api/modeling/tables/{table_id}/records/{id}`             | 删除表数据                                        | `views_records.RecordDeleteView`          | `EmptySerializer`               | `record_service.delete_record()`             | TABLE_DATA:MANAGE |
| GET    | `/api/modeling/tables/{table_id}/records/{id}`             | 表数据详情（行/列权限应用）                       | `views_records.RecordDetailView`          | `RecordReadSerializer`          | `record_service.get_record()`                | TABLE_DATA:VIEW   |
| PATCH  | `/api/modeling/tables/{table_id}/records/{id}`             | 更新表数据（列只读校验）                          | `views_records.RecordUpdateView`          | `RecordWriteSerializer`         | `record_service.update_record()`             | TABLE_DATA:EDIT   |

---

# query_engine ｜查询引擎

**模块定位**：FilterDSL/QueryConfig 的校验、SQL 编译与执行；供建模、报表、预览、导出复用。

## 目录结构

```text
src/apps/query_engine/
├── __init__.py
├── dsl.py                    # FilterDSL 入口（调用 common.dsl）
├── compiler/
│   ├── __init__.py
│   ├── query_config.py
│   └── dataset.py
├── runner/
│   ├── __init__.py
│   ├── constraints.py
│   └── query_runner.py
├── services.py               # validate/run/export（供 api/query/* 与 modeling 复用）
└── api/
    ├──_apply_views_in_api_package_only_.txt  # 说明：query API 统一挂在 apps/query_engine/api 下（可选）
```

## 模型（与 tech.md 数据表对齐）

本模块原则上不落独立业务表（仅复用各模块元数据与 DW 表），主要负责编译与执行。

## Services（用例层：写操作）

- `services.py`
  - `validate()`：校验 FilterDSL / QueryConfig
  - `run()`：编译 SQL + 注入权限约束 + 执行（`integrations.dw.client`）
  - `export_csv()`：创建 ExportJob（reports.export_job）并提交执行任务

## API（接口清单与代码落点）

| 方法 | 路径                    | 说明                                   | View（views\_\*.py）        | Serializer                | Service（函数）              | 权限                 |
| ---- | ----------------------- | -------------------------------------- | --------------------------- | ------------------------- | ---------------------------- | -------------------- |
| POST | `/api/query/export/csv` | 导出 CSV（创建 export_job + 异步）     | `views_query.ExportCsvView` | `QueryExportSerializer`   | `query_service.export_csv()` | 登录态（资源权限内） |
| POST | `/api/query/run`        | 执行查询（叠加权限约束）               | `views_query.RunView`       | `QueryRunSerializer`      | `query_service.run()`        | 登录态（资源权限内） |
| POST | `/api/query/validate`   | 校验 FilterDSL / QueryConfig（不执行） | `views_query.ValidateView`  | `QueryValidateSerializer` | `query_service.validate()`   | 登录态               |

---

# execution ｜执行框架

**模块定位**：TaskRunInstance + Scheduler + Worker；为 DatasetRefresh/Export/FlowRun 等提供统一执行底座。

## 目录结构

```text
src/apps/execution/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── task_run.py            # TaskRunInstance（task_run_instance）
│   └── task_log.py            # TaskRunLog（task_run_log，可选）
├── registry/
│   ├── __init__.py
│   └── tasks.py               # task_type -> handler 注册
├── scheduler/
│   ├── __init__.py
│   └── dispatcher.py
├── worker/
│   ├── __init__.py
│   └── base.py
└── management/
    └── commands/
        └── scheduler_tick.py
```

## 模型（与 tech.md 数据表对齐）

| 文件                 | 模型              | db_table            | 说明                                                                |
| -------------------- | ----------------- | ------------------- | ------------------------------------------------------------------- |
| `models/task_run.py` | `TaskRunInstance` | `task_run_instance` | 通用任务运行实体：task_type/task_id/status/started/finished/error。 |
| `models/task_log.py` | `TaskRunLog`      | `task_run_log`      | 可选：统一 run 日志（若各业务 run 表已足够可不建）。                |

## Services（用例层：写操作）

执行框架多为基础设施代码：

- `registry/tasks.py`：注册 task_type -> handler（业务模块在 AppConfig.ready() 注册）
- `scheduler/dispatcher.py`：把 TaskRunInstance 投递到队列
- `management/commands/scheduler_tick.py`：定时扫描 cron 触发（Flow/Dataset）并创建 TaskRunInstance
- `worker/base.py`：handler 基类与上下文（tenant_id/request_id）

## API（接口清单与代码落点）

| 方法 | 路径 | 说明 | View（views\_\*.py） | Serializer | Service（函数） | 权限 |
| ---- | ---- | ---- | -------------------- | ---------- | --------------- | ---- |

---

# reports ｜报表链路

**模块定位**：Dataset（物化表）→ Chart → Dashboard；支持 refresh_run 与 export_job。

## 目录结构

```text
src/apps/reports/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── dataset.py            # Dataset（dataset）
│   ├── dataset_refresh_run.py # DatasetRefreshRun（dataset_refresh_run）
│   ├── chart.py              # Chart（chart）
│   ├── dashboard.py          # Dashboard（dashboard）
│   ├── dashboard_item.py     # DashboardItem（dashboard_item）
│   └── export_job.py         # ExportJob（export_job）
├── services/
│   ├── __init__.py
│   ├── datasets.py
│   ├── charts.py
│   ├── dashboards.py
│   └── exports.py
├── workers/
│   ├── __init__.py
│   ├── dataset_refresh.py
│   └── export_job.py
├── api/
│   ├── __init__.py
│   ├── serializers_datasets.py
│   ├── serializers_charts.py
│   ├── serializers_dashboards.py
│   ├── serializers_exports.py
│   ├── permissions.py
│   ├── views_datasets.py
│   ├── views_charts.py
│   ├── views_dashboards.py
│   ├── views_exports.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                            | 模型                | db_table              | 说明                                                          |
| ------------------------------- | ------------------- | --------------------- | ------------------------------------------------------------- |
| `models/dataset.py`             | `Dataset`           | `dataset`             | Dataset 定义：base_table/base_filter/cron/enabled/status 等。 |
| `models/dataset_refresh_run.py` | `DatasetRefreshRun` | `dataset_refresh_run` | 刷新运行记录：status/row_count/duration/error。               |
| `models/chart.py`               | `Chart`             | `chart`               | Chart：dataset_id + query_config_json + viz_config_json。     |
| `models/dashboard.py`           | `Dashboard`         | `dashboard`           | Dashboard：layout_json + 基本信息。                           |
| `models/dashboard_item.py`      | `DashboardItem`     | `dashboard_item`      | 仪表盘元素：引用 chart + 位置信息。                           |
| `models/export_job.py`          | `ExportJob`         | `export_job`          | 导出任务：type/status/file_url/created_by。                   |

## Services（用例层：写操作）

- `services/datasets.py`
  - `list()` / `create()` / `get()` / `update()`
  - `set_enabled()`：启停 cron
  - `preview()`：不落库预览
  - `refresh()`：创建 DatasetRefreshRun + 提交 TaskRunInstance
  - `list_refresh_runs()`
- `services/charts.py`
  - `list()` / `create()` / `get()` / `update()` / `delete()`
  - `preview()`：调用 QueryEngine
- `services/dashboards.py`
  - `list()` / `create()` / `get()` / `update()` / `set_layout()`
  - `add_item()` / `update_item()` / `remove_item()`
  - `render()`：批量执行 charts
- `services/exports.py`
  - `create_for_chart()` / `get_job()`
- `workers/dataset_refresh.py`：DW tmp -> swap（原子替换）
- `workers/export_job.py`：生成文件并上传 storage

## API（接口清单与代码落点）

| 方法   | 路径                                                       | 说明                                                 | View（views\_\*.py）                       | Serializer                      | Service（函数）                       | 权限           |
| ------ | ---------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------ | ------------------------------- | ------------------------------------- | -------------- |
| GET    | `/api/charts`                                              | Chart 列表                                           | `views_charts.ChartListView`               | `ChartSerializer`               | `chart_service.list()`                | CHART:VIEW     |
| POST   | `/api/charts`                                              | 创建 Chart（query_config_json + viz_config_json）    | `views_charts.ChartCreateView`             | `ChartCreateSerializer`         | `chart_service.create()`              | CHART:EDIT     |
| POST   | `/api/charts/preview`                                      | Chart 预览（执行 QueryConfig）                       | `views_charts.ChartPreviewView`            | `ChartPreviewSerializer`        | `chart_service.preview()`             | CHART:VIEW     |
| DELETE | `/api/charts/{chart_id}`                                   | 删除 Chart                                           | `views_charts.ChartDeleteView`             | `EmptySerializer`               | `chart_service.delete()`              | CHART:MANAGE   |
| GET    | `/api/charts/{chart_id}`                                   | Chart 详情                                           | `views_charts.ChartDetailView`             | `ChartDetailSerializer`         | `chart_service.get()`                 | CHART:VIEW     |
| PATCH  | `/api/charts/{chart_id}`                                   | 编辑 Chart                                           | `views_charts.ChartUpdateView`             | `ChartUpdateSerializer`         | `chart_service.update()`              | CHART:EDIT     |
| POST   | `/api/charts/{chart_id}/exports`                           | 创建图表导出任务（export_job）                       | `views_charts.ChartExportCreateView`       | `ChartExportSerializer`         | `export_service.create_for_chart()`   | CHART:VIEW     |
| GET    | `/api/dashboards`                                          | Dashboard 列表                                       | `views_dashboards.DashboardListView`       | `DashboardSerializer`           | `dashboard_service.list()`            | DASHBOARD:VIEW |
| POST   | `/api/dashboards`                                          | 创建 Dashboard                                       | `views_dashboards.DashboardCreateView`     | `DashboardCreateSerializer`     | `dashboard_service.create()`          | DASHBOARD:EDIT |
| GET    | `/api/dashboards/{dashboard_id}`                           | Dashboard 详情                                       | `views_dashboards.DashboardDetailView`     | `DashboardDetailSerializer`     | `dashboard_service.get()`             | DASHBOARD:VIEW |
| PATCH  | `/api/dashboards/{dashboard_id}`                           | 编辑 Dashboard 基本信息                              | `views_dashboards.DashboardUpdateView`     | `DashboardUpdateSerializer`     | `dashboard_service.update()`          | DASHBOARD:EDIT |
| POST   | `/api/dashboards/{dashboard_id}/items`                     | 添加 DashboardItem（引用 chart）                     | `views_dashboards.DashboardItemCreateView` | `DashboardItemCreateSerializer` | `dashboard_service.add_item()`        | DASHBOARD:EDIT |
| DELETE | `/api/dashboards/{dashboard_id}/items/{dashboard_item_id}` | 删除 DashboardItem                                   | `views_dashboards.DashboardItemDeleteView` | `EmptySerializer`               | `dashboard_service.remove_item()`     | DASHBOARD:EDIT |
| PATCH  | `/api/dashboards/{dashboard_id}/items/{dashboard_item_id}` | 更新 DashboardItem（位置/尺寸等）                    | `views_dashboards.DashboardItemUpdateView` | `DashboardItemUpdateSerializer` | `dashboard_service.update_item()`     | DASHBOARD:EDIT |
| PUT    | `/api/dashboards/{dashboard_id}/layout`                    | 覆盖更新 layout_json                                 | `views_dashboards.DashboardLayoutPutView`  | `DashboardLayoutSerializer`     | `dashboard_service.set_layout()`      | DASHBOARD:EDIT |
| POST   | `/api/dashboards/{dashboard_id}/render`                    | 渲染 Dashboard（批量执行 charts）                    | `views_dashboards.DashboardRenderView`     | `DashboardRenderSerializer`     | `dashboard_service.render()`          | DASHBOARD:VIEW |
| GET    | `/api/dashboards/{id}`                                     | （见 tech.md 描述）                                  | `TBD`                                      | `TBD`                           | `TBD`                                 | TBD            |
| PUT    | `/api/dashboards/{id}/layout`                              | （见 tech.md 描述）                                  | `TBD`                                      | `TBD`                           | `TBD`                                 | TBD            |
| GET    | `/api/datasets`                                            | Dataset 列表                                         | `views_datasets.DatasetListView`           | `DatasetSerializer`             | `dataset_service.list()`              | DATASET:VIEW   |
| POST   | `/api/datasets`                                            | 创建 Dataset（定义 base_table + base_filter + cron） | `views_datasets.DatasetCreateView`         | `DatasetCreateSerializer`       | `dataset_service.create()`            | DATASET:MANAGE |
| GET    | `/api/datasets/{dataset_id}`                               | Dataset 详情                                         | `views_datasets.DatasetDetailView`         | `DatasetDetailSerializer`       | `dataset_service.get()`               | DATASET:VIEW   |
| PATCH  | `/api/datasets/{dataset_id}`                               | 编辑 Dataset                                         | `views_datasets.DatasetUpdateView`         | `DatasetUpdateSerializer`       | `dataset_service.update()`            | DATASET:EDIT   |
| POST   | `/api/datasets/{dataset_id}/enable`                        | 启用/禁用 Dataset 调度                               | `views_datasets.DatasetEnableView`         | `DatasetEnableSerializer`       | `dataset_service.set_enabled()`       | DATASET:MANAGE |
| POST   | `/api/datasets/{dataset_id}/preview`                       | 预览 Dataset（不落库）                               | `views_datasets.DatasetPreviewView`        | `DatasetPreviewSerializer`      | `dataset_service.preview()`           | DATASET:VIEW   |
| POST   | `/api/datasets/{dataset_id}/refresh`                       | 手动触发 refresh（提交 TaskRunInstance）             | `views_datasets.DatasetRefreshView`        | `EmptySerializer`               | `dataset_service.refresh()`           | DATASET:EDIT   |
| GET    | `/api/datasets/{dataset_id}/refresh-runs`                  | 刷新运行历史                                         | `views_datasets.DatasetRefreshRunListView` | `DatasetRefreshRunSerializer`   | `dataset_service.list_refresh_runs()` | DATASET:VIEW   |
| POST   | `/api/datasets/{id}/refresh`                               | （见 tech.md 描述）                                  | `TBD`                                      | `TBD`                           | `TBD`                                 | TBD            |
| GET    | `/api/exports/{export_job_id}`                             | 导出任务详情（状态/file_url）                        | `views_exports.ExportJobDetailView`        | `ExportJobSerializer`           | `export_service.get_job()`            | 对应资源:VIEW  |

---

# flows ｜ Flow DAG 与运行

**模块定位**：Flow DAG（nodes/edges）+ cron 调度 + run/node_run/log；支持手动触发与查询。

## 目录结构

```text
src/apps/flows/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── flow.py               # Flow（flow）
│   ├── node.py               # FlowNode（flow_node）
│   ├── edge.py               # FlowEdge（flow_edge）
│   ├── run.py                # FlowRun（flow_run）
│   ├── node_run.py           # FlowNodeRun（flow_node_run）
│   └── run_log.py            # FlowRunLog（flow_run_log）
├── services/
│   ├── __init__.py
│   ├── flows.py
│   ├── graph.py
│   ├── schedule.py
│   └── runs.py
├── api/
│   ├── __init__.py
│   ├── serializers_flows.py
│   ├── serializers_graph.py
│   ├── serializers_runs.py
│   ├── permissions.py
│   ├── views_flows.py
│   ├── views_graph.py
│   ├── views_schedule.py
│   ├── views_runs.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                 | 模型          | db_table        | 说明                                                     |
| -------------------- | ------------- | --------------- | -------------------------------------------------------- |
| `models/flow.py`     | `Flow`        | `flow`          | Flow 主表：name/desc/enabled/cron/timezone。             |
| `models/node.py`     | `FlowNode`    | `flow_node`     | DAG 节点：type/config/position。                         |
| `models/edge.py`     | `FlowEdge`    | `flow_edge`     | DAG 边：from/to；保存时需 DAG 校验（无环/无自环）。      |
| `models/run.py`      | `FlowRun`     | `flow_run`      | 运行实例：trigger_type/status/started/finished/summary。 |
| `models/node_run.py` | `FlowNodeRun` | `flow_node_run` | 节点运行：status/output/error。                          |
| `models/run_log.py`  | `FlowRunLog`  | `flow_run_log`  | 运行日志：SCHEDULE_SKIP/ERROR 等。                       |

## Services（用例层：写操作）

- `services/flows.py`
  - `list()` / `create()` / `get()` / `update()` / `delete()` / `tree()`
- `services/graph.py`
  - `get_graph()` / `save_graph()` / `validate_graph()`（DAG 校验、node_config 校验）
- `services/schedule.py`
  - `get()` / `update()`：cron/enabled/timezone/next_run_at
- `services/runs.py`
  - `trigger()` / `list_runs()` / `get_run()`
  - `list_node_runs()` / `get_node_run()` / `list_run_logs()` / `list_flow_logs()`
- 与租户停用联动：Tenant=SUSPENDED 时禁止触发新的 Run（scheduler_tick 层 + trigger 层双保险）。

## API（接口清单与代码落点）

| 方法   | 路径                                | 说明                              | View（views\_\*.py）                  | Serializer                    | Service（函数）                 | 权限        |
| ------ | ----------------------------------- | --------------------------------- | ------------------------------------- | ----------------------------- | ------------------------------- | ----------- |
| GET    | `/api/flow-node-runs/{node_run_id}` | NodeRun 详情                      | `views_flow_runs.NodeRunDetailView`   | `NodeRunDetailSerializer`     | `run_service.get_node_run()`    | FLOW:VIEW   |
| GET    | `/api/flow-runs/{run_id}`           | FlowRun 详情                      | `views_flow_runs.FlowRunDetailView`   | `FlowRunDetailSerializer`     | `run_service.get_run()`         | FLOW:VIEW   |
| GET    | `/api/flow-runs/{run_id}/logs`      | FlowRun 日志                      | `views_flow_runs.FlowRunLogListView`  | `FlowRunLogSerializer`        | `run_service.list_run_logs()`   | FLOW:VIEW   |
| GET    | `/api/flow-runs/{run_id}/node-runs` | NodeRun 列表                      | `views_flow_runs.NodeRunListView`     | `NodeRunSerializer`           | `run_service.list_node_runs()`  | FLOW:VIEW   |
| GET    | `/api/flows`                        | Flow 列表                         | `views_flows.FlowListView`            | `FlowSerializer`              | `flow_service.list()`           | FLOW:VIEW   |
| POST   | `/api/flows`                        | 创建 Flow                         | `views_flows.FlowCreateView`          | `FlowCreateSerializer`        | `flow_service.create()`         | FLOW:EDIT   |
| GET    | `/api/flows/tree`                   | Flow 树（资源树视图）             | `views_flows.FlowTreeView`            | `FlowTreeSerializer`          | `flow_service.tree()`           | FLOW:VIEW   |
| DELETE | `/api/flows/{flow_id}`              | 删除 Flow                         | `views_flows.FlowDeleteView`          | `EmptySerializer`             | `flow_service.delete()`         | FLOW:MANAGE |
| GET    | `/api/flows/{flow_id}`              | Flow 详情                         | `views_flows.FlowDetailView`          | `FlowDetailSerializer`        | `flow_service.get()`            | FLOW:VIEW   |
| PATCH  | `/api/flows/{flow_id}`              | 编辑 Flow 基本信息                | `views_flows.FlowUpdateView`          | `FlowUpdateSerializer`        | `flow_service.update()`         | FLOW:EDIT   |
| GET    | `/api/flows/{flow_id}/graph`        | 获取 DAG（nodes/edges）           | `views_flow_graph.GraphGetView`       | `FlowGraphSerializer`         | `flow_service.get_graph()`      | FLOW:VIEW   |
| PUT    | `/api/flows/{flow_id}/graph`        | 保存 DAG（需 DAG 校验）           | `views_flow_graph.GraphPutView`       | `FlowGraphPutSerializer`      | `flow_service.save_graph()`     | FLOW:EDIT   |
| GET    | `/api/flows/{flow_id}/logs`         | Flow 运行日志（近 N 条）          | `views_flow_runs.FlowLogsView`        | `FlowLogSerializer`           | `run_service.list_logs()`       | FLOW:VIEW   |
| GET    | `/api/flows/{flow_id}/runs`         | FlowRun 列表                      | `views_flow_runs.FlowRunListView`     | `FlowRunSerializer`           | `run_service.list_runs()`       | FLOW:VIEW   |
| POST   | `/api/flows/{flow_id}/runs`         | 手动触发一次 FlowRun              | `views_flow_runs.FlowRunTriggerView`  | `EmptySerializer`             | `run_service.trigger()`         | FLOW:EDIT   |
| GET    | `/api/flows/{flow_id}/schedule`     | 读取调度信息（cron/next_run）     | `views_flow_schedule.ScheduleGetView` | `FlowScheduleSerializer`      | `schedule_service.get()`        | FLOW:VIEW   |
| PUT    | `/api/flows/{flow_id}/schedule`     | 更新调度（cron/enabled/timezone） | `views_flow_schedule.SchedulePutView` | `FlowSchedulePutSerializer`   | `schedule_service.update()`     | FLOW:MANAGE |
| POST   | `/api/flows/{flow_id}/validate`     | 校验 DAG 与 node_config           | `views_flow_graph.GraphValidateView`  | `FlowGraphValidateSerializer` | `flow_service.validate_graph()` | FLOW:EDIT   |
| PUT    | `/api/flows/{id}/graph`             | （见 tech.md 描述）               | `TBD`                                 | `TBD`                         | `TBD`                           | TBD         |
| POST   | `/api/flows/{id}/runs`              | （见 tech.md 描述）               | `TBD`                                 | `TBD`                         | `TBD`                           | TBD         |

---

# notifications ｜通知

**模块定位**：站内通知列表/未读数/标记已读。

## 目录结构

```text
src/apps/notifications/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   └── notification.py       # Notification（notification，可按 tech 命名）
├── selectors.py
├── services.py
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views_notifications.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                     | 模型           | db_table       | 说明                                                                        |
| ------------------------ | -------------- | -------------- | --------------------------------------------------------------------------- |
| `models/notification.py` | `Notification` | `notification` | 站内通知：entity_type/entity_id/title/body/read_at 等（按 tech 结构实现）。 |

## Services（用例层：写操作）

- `services.py`
  - `list(unread_only, limit, offset)`
  - `unread_count()`
  - `mark_read(ids|all_before)`（支持批量）

## API（接口清单与代码落点）

| 方法 | 路径                              | 说明                         | View（views\_\*.py）                       | Serializer               | Service（函数）                | 权限   |
| ---- | --------------------------------- | ---------------------------- | ------------------------------------------ | ------------------------ | ------------------------------ | ------ |
| GET  | `/api/notifications`              | 通知列表（unread_only/分页） | `views_notifications.NotificationListView` | `NotificationSerializer` | `notif_service.list()`         | 登录态 |
| POST | `/api/notifications/mark-read`    | 标记已读（批量）             | `views_notifications.MarkReadView`         | `MarkReadSerializer`     | `notif_service.mark_read()`    | 登录态 |
| GET  | `/api/notifications/unread-count` | 未读数量                     | `views_notifications.UnreadCountView`      | `EmptySerializer`        | `notif_service.unread_count()` | 登录态 |

---

# audit_logs ｜审计

**模块定位**：审计日志查询（租户内）+ 元数据枚举（actions/target-types）。

## 目录结构

```text
src/apps/audit_logs/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   └── audit_log.py          # AuditLog（audit_log）
├── selectors.py
├── services/
│   ├── __init__.py
│   ├── audit.py              # list/get（tenant）
│   └── meta.py               # actions/target-types（tenant）
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── views_audit.py
│   ├── views_meta.py
│   └── urls.py
├── migrations/
└── tests/
```

## 模型（与 tech.md 数据表对齐）

| 文件                  | 模型       | db_table    | 说明                                                                          |
| --------------------- | ---------- | ----------- | ----------------------------------------------------------------------------- |
| `models/audit_log.py` | `AuditLog` | `audit_log` | 审计日志：actor/tenant/action_type/target_type/target_id/diff/result/reason。 |

## Services（用例层：写操作）

- `services/audit.py`
  - `list()`：按时间/actor/action/target 过滤
  - `get()`：详情
- `services/meta.py`
  - `actions()`：操作类型枚举（前端筛选器用）
  - `target_types()`：目标类型枚举
- 写入统一走 `common.audit.emitter.emit()`（不要在此处散写）。

## API（接口清单与代码落点）

| 方法 | 路径                                | 说明                  | View（views\_\*.py）             | Serializer                 | Service（函数）                     | 权限             |
| ---- | ----------------------------------- | --------------------- | -------------------------------- | -------------------------- | ----------------------------------- | ---------------- |
| GET  | `/api/audit-logs`                   | 审计列表（tenant 内） | `views_audit.AuditLogListView`   | `AuditLogSerializer`       | `audit_service.list()`              | owner-only（V1） |
| GET  | `/api/audit-logs/meta/actions`      | 操作类型枚举（分组）  | `views_meta.ActionsMetaView`     | `ActionMetaSerializer`     | `audit_meta_service.actions()`      | owner-only（V1） |
| GET  | `/api/audit-logs/meta/target-types` | 目标类型枚举          | `views_meta.TargetTypesMetaView` | `TargetTypeMetaSerializer` | `audit_meta_service.target_types()` | owner-only（V1） |
| GET  | `/api/audit-logs/{audit_id}`        | 审计详情              | `views_audit.AuditLogDetailView` | `AuditLogDetailSerializer` | `audit_service.get()`               | owner-only（V1） |
| GET  | `/api/audit-logs/{id}`              | （见 tech.md 描述）   | `TBD`                            | `TBD`                      | `TBD`                               | TBD              |

---

# platform_admin ｜平台后台

**模块定位**：平台管理员 API：GlobalUser/Tenant/TenantUser 管理（/admin/api/_）与平台审计（/api/platform/audit-logs_）。

## 目录结构

```text
src/apps/platform_admin/
├── __init__.py
├── apps.py
├── services/
│   ├── __init__.py
│   ├── users.py              # GlobalUser 管理
│   ├── tenants.py            # Tenant 管理 + 状态联动 Scheduler
│   ├── tenant_users.py       # TenantUser 管理（批量添加/移除/设 owner/改角色）
│   └── platform_audit.py     # /api/platform/audit-logs*
├── api/
│   ├── __init__.py
│   ├── serializers_users.py
│   ├── serializers_tenants.py
│   ├── serializers_tenant_users.py
│   ├── serializers_platform_audit.py
│   ├── permissions.py        # IsPlatformAdmin（复用 accounts.api.permissions 可选）
│   ├── views_users.py
│   ├── views_tenants.py
│   ├── views_tenant_users.py
│   ├── views_platform_audit.py
│   └── urls.py
└── tests/
```

## 模型（与 tech.md 数据表对齐）

本模块不新增核心业务表：

- 复用 `accounts.GlobalUser`、`tenants.Tenant`、`tenants.TenantUser`、`audit_logs.AuditLog`。

## Services（用例层：写操作）

- `services/users.py`
  - `list_users()` / `create_user()` / `update_user()` / `enable()` / `disable()` / `reset_password()`
- `services/tenants.py`
  - `list_tenants()` / `create_tenant()` / `update_tenant(name/plan/status)` / `enable()` / `suspend()`
  - `suspend()` 必须联动停止该租户调度触发（Flow）
- `services/tenant_users.py`
  - `list()` / `add_users(batch)` / `update(status/owner/roles)` / `remove()`
- `services/platform_audit.py`
  - `list()` / `get()`（跨租户审计查询）
  - `meta.actions()` / `meta.target_types()`

## API（接口清单与代码落点）

| 方法   | 路径                                                 | 说明                                                           | View（views\_\*.py）                               | Serializer                        | Service（函数）                         | 权限            |
| ------ | ---------------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------- | --------------------------------- | --------------------------------------- | --------------- |
| GET    | `/admin/api/tenants`                                 | Tenant 列表（搜索/筛选）                                       | `views_tenants.AdminTenantListView`                | `AdminTenantListSerializer`       | `admin_tenant_service.list_tenants()`   | IsPlatformAdmin |
| POST   | `/admin/api/tenants`                                 | 创建 Tenant（code/name/plan/status）                           | `views_tenants.AdminTenantCreateView`              | `AdminTenantCreateSerializer`     | `admin_tenant_service.create_tenant()`  | IsPlatformAdmin |
| PATCH  | `/admin/api/tenants/{id}`                            | 编辑 Tenant（必须支持改 name；plan/status；code 不可改）       | `views_tenants.AdminTenantUpdateView`              | `AdminTenantUpdateSerializer`     | `admin_tenant_service.update_tenant()`  | IsPlatformAdmin |
| POST   | `/admin/api/tenants/{id}/enable`                     | 启用 Tenant                                                    | `views_tenants.AdminTenantEnableView`              | `EmptySerializer`                 | `admin_tenant_service.enable()`         | IsPlatformAdmin |
| POST   | `/admin/api/tenants/{id}/suspend`                    | 停用 Tenant（需停止该租户 Flow 调度）                          | `views_tenants.AdminTenantSuspendView`             | `EmptySerializer`                 | `admin_tenant_service.suspend()`        | IsPlatformAdmin |
| GET    | `/admin/api/tenants/{tenantId}/users`                | 租户成员列表（TenantUser）                                     | `views_tenant_users.AdminTenantUserListView`       | `AdminTenantUserSerializer`       | `admin_tenant_user_service.list()`      | IsPlatformAdmin |
| POST   | `/admin/api/tenants/{tenantId}/users`                | 添加成员（从 GlobalUser 选择，可批量，可设 owner/初始角色）    | `views_tenant_users.AdminTenantUserCreateView`     | `AdminTenantUserCreateSerializer` | `admin_tenant_user_service.add_users()` | IsPlatformAdmin |
| DELETE | `/admin/api/tenants/{tenantId}/users/{tenantUserId}` | 移除成员（删除 TenantUser）                                    | `views_tenant_users.AdminTenantUserDeleteView`     | `EmptySerializer`                 | `admin_tenant_user_service.remove()`    | IsPlatformAdmin |
| PATCH  | `/admin/api/tenants/{tenantId}/users/{tenantUserId}` | 修改成员（status/owner/roles）                                 | `views_tenant_users.AdminTenantUserUpdateView`     | `AdminTenantUserUpdateSerializer` | `admin_tenant_user_service.update()`    | IsPlatformAdmin |
| GET    | `/admin/api/users`                                   | GlobalUser 列表（搜索/筛选）                                   | `views_users.AdminUserListView`                    | `AdminUserListSerializer`         | `admin_user_service.list_users()`       | IsPlatformAdmin |
| POST   | `/admin/api/users`                                   | 创建 GlobalUser（含初始密码策略）                              | `views_users.AdminUserCreateView`                  | `AdminUserCreateSerializer`       | `admin_user_service.create_user()`      | IsPlatformAdmin |
| PATCH  | `/admin/api/users/{id}`                              | 编辑 GlobalUser（display_name/email/is_platform_admin/status） | `views_users.AdminUserUpdateView`                  | `AdminUserUpdateSerializer`       | `admin_user_service.update_user()`      | IsPlatformAdmin |
| POST   | `/admin/api/users/{id}/disable`                      | 禁用 GlobalUser                                                | `views_users.AdminUserDisableView`                 | `EmptySerializer`                 | `admin_user_service.disable()`          | IsPlatformAdmin |
| POST   | `/admin/api/users/{id}/enable`                       | 启用 GlobalUser                                                | `views_users.AdminUserEnableView`                  | `EmptySerializer`                 | `admin_user_service.enable()`           | IsPlatformAdmin |
| POST   | `/admin/api/users/{id}/reset_password`               | 重置密码（可选）                                               | `views_users.AdminUserResetPasswordView`           | `AdminResetPasswordSerializer`    | `admin_user_service.reset_password()`   | IsPlatformAdmin |
| GET    | `/api/platform/audit-logs`                           | 平台审计列表（跨租户）                                         | `views_platform_audit.PlatformAuditListView`       | `PlatformAuditListSerializer`     | `platform_audit_service.list()`         | IsPlatformAdmin |
| GET    | `/api/platform/audit-logs/meta/actions`              | 平台审计 actions 枚举                                          | `views_platform_audit.PlatformActionsMetaView`     | `ActionMetaSerializer`            | `platform_audit_meta.actions()`         | IsPlatformAdmin |
| GET    | `/api/platform/audit-logs/meta/target-types`         | 平台审计 target-types 枚举                                     | `views_platform_audit.PlatformTargetTypesMetaView` | `TargetTypeMetaSerializer`        | `platform_audit_meta.target_types()`    | IsPlatformAdmin |
| GET    | `/api/platform/audit-logs/{audit_id}`                | 平台审计详情                                                   | `views_platform_audit.PlatformAuditDetailView`     | `PlatformAuditDetailSerializer`   | `platform_audit_service.get()`          | IsPlatformAdmin |

---

# assist ｜ LLM 辅助

**模块定位**：提供编码/命名建议的辅助接口（可失败降级）。

## 目录结构

```text
src/apps/assist/
├── __init__.py
├── apps.py
├── services.py               # 调用 integrations.llm.client（可降级）
└── api/
    ├── __init__.py
    ├── serializers.py
    ├── views_assist.py
    └── urls.py
```

## 模型（与 tech.md 数据表对齐）

本模块不落库或仅落轻量配置表（如需）。V1 以调用 LLM client 返回建议为主。

## Services（用例层：写操作）

- `services.py`
  - `code_suggest()`：输入上下文（表/字段/DSL/命名）-> 返回建议（可失败降级：本地规则生成）

## API（接口清单与代码落点）

| 方法 | 路径                       | 说明              | View（views\_\*.py）           | Serializer              | Service（函数）                 | 权限           |
| ---- | -------------------------- | ----------------- | ------------------------------ | ----------------------- | ------------------------------- | -------------- |
| POST | `/api/assist/code-suggest` | LLM 编码/命名建议 | `views_assist.CodeSuggestView` | `CodeSuggestSerializer` | `assist_service.code_suggest()` | 登录态（可选） |

---

## 4. 实施清单（给编程模型的“落地步骤”）

1. 按上述目录创建包与空文件；确保 `config/settings/base.py` 正确装载 INSTALLED_APPS。
2. 先实现 `accounts`（登录/刷新/退出 + TenantContext 注入）。
3. 实现 `iam` 的 PermissionEngine 与 FilterDSL 编译（common.dsl → SQL）。
4. 实现 `resource_tree`（scope 分树）与 `modeling`（表/字段 + DW DDL）。
5. 实现 `query_engine`（validate/run/export）并在 modeling/reports 复用。
6. 实现 `execution`（TaskRunInstance + dispatcher + worker handler 注册）。
7. 实现 `reports`（dataset_refresh_run + export_job + worker）。
8. 实现 `flows`（graph 校验 + schedule + run/node_run/log）。
9. 实现 `audit_logs` 与 `platform_admin`，并补齐平台侧接口组与审计 meta 接口。

> 备注：如发现 tech.md 中新增/调整接口或表字段，应以 tech.md 为准更新本文件；禁止“实现少做”。
