
## 0. 目标与约束

本文件用于**指导后端代码实现**：目录结构、文件职责、模型归属、服务划分、接口清单与代码落点。所有接口清单以 `tech.md` 为准（文档里标注“必须实现”的均视为硬要求）。

### 0.1 硬约束（实现必须满足）

- **目录职责清晰**
  - `src/`：业务代码根目录
  - `config/`：仅放 Django 项目配置（settings/urls/asgi/wsgi/celery/logging）
  - `apps/`：仅放业务域（Domain）代码
  - `common/`：横切能力（错误/审计/DSL/上下文/中间件/工具）
  - `integrations/`：外部系统适配（DW/Storage/LLM…）
- **分层与写路径**
  - 业务写操作必须走 `services/*`（用例层）
  - 只读查询走 `selectors.py`（Query 层）
  - 禁止 View 直接写数据库（避免绕开权限/审计/一致性策略）
- **权限强制执行（后端兜底）**
  - 资源级（RolePermission）+ 行级（RowPermission）+ 列级（ColumnPermission）必须强制执行
  - QueryEngine / 记录读取必须叠加行列权限约束
- **审计强制**
  - 权限变更、关键配置变更（Flow/Modeling/Reports）必须写审计（见 `common.audit.emitter`）
- **平台后台强隔离**
  - 所有 `/admin/*` 与 `/admin/api/*` 仅允许 `is_platform_admin=true` 用户访问，否则 403

---

## 1. 总体目录树（ASCII Tree）

> 说明：`tests/` 将采用“模块内单测 + 顶层集成测”的混合策略（见第 2.3 节）。

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
    └── tests/                  # 仅放集成/冒烟/E2E（不要把所有单测堆这里）
        ├── __init__.py
        └── smoke/
            └── test_smoke.py
```

---

## 2. 分层与依赖方向（防循环依赖）

### 2.1 模块职责

- `config/`：Django 项目配置（settings/urls/asgi/wsgi/celery/logging）。
- `common/`：跨领域基础能力（TenantContext、统一错误码、FilterDSL 编译、审计 emitter、middleware 等）。
- `integrations/`：外部系统适配（DW、存储、LLM）。
- `apps/*`：按业务域拆分（accounts/tenants/iam/modeling/flows/reports/…）。
- `tests/`：系统级集成测试与冒烟测试（跨模块链路验证）。

### 2.2 依赖规则（必须遵守）

1. `apps/*` **可以依赖** `common/` 与 `integrations/`。
2. `apps/A` 与 `apps/B` 互相调用时：
   - **优先**通过 `selectors.py`（只读）或 `services` 中对外暴露的“稳定接口函数”。
   - **禁止**直接 import 对方 models 进行复杂业务操作（易破坏事务/权限/审计）。
3. `execution/` **不反向依赖** `reports/flows/modeling`：通过 `execution.registry.tasks` 做 handler 注册反转依赖。
4. `common/` 不允许 import `apps/*`（避免 common 变成“大而全业务层”）。

### 2.3 测试组织规则（强制执行）

为避免 `src/tests/` 爆炸式增长，采用 **“模块内单测 + 顶层集成测”**：

- ✅ **模块内 tests/**（单元测试 & 该模块 API 测试）
  - 放置位置：`src/apps/<app_name>/tests/`
  - 适用范围：只依赖本模块（或可通过 mock 隔离外部模块）
- ✅ **顶层 src/tests/**（跨模块集成 / E2E / 冒烟）
  - 放置位置：`src/tests/integration/`、`src/tests/e2e/`、`src/tests/smoke/`
  - 适用范围：涉及多个 app 的链路测试、真实 DB/Redis/Celery 的组合测试

> 规则：**谁的逻辑，就把测试放谁旁边；跨模块行为，放顶层 `src/tests/`。**

---

## 3. apps 清单（与 tech.md 模块映射）

- `accounts`：平台用户与会话（GlobalUser/AuthSession）；`/api/auth/*`、`/api/me`
- `tenants`：租户（Tenant）与成员实体（TenantUser）；`/api/tenants`、`/api/tenants/switch`
- `iam`：租户内角色与权限（Role/RolePermission/RowPermission/ColumnPermission）
- `resource_tree`：资源树（ResourceTreeNode），对接 TABLE/FLOW/DATASET/DASHBOARD 等 scope
- `modeling`：建模（ModelingTable/ModelingField + 记录 CRUD + REFERENCE 推导关系）
- `query_engine`：Query/Filter 编译与执行；`/api/query/*`
- `execution`：统一执行框架（TaskRunInstance + scheduler/worker）
- `reports`：Dataset/Chart/Dashboard/ExportJob/DatasetRefreshRun
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
| GET  | `/api/me`           | 获取当前用户信息（含 tenant 上下文）          | `views_me.MeView`        | `MeSerializer`      | `account_selector.get_me_payload()` | 登录态         |

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
    └── __init__.py
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

**模块定位**：租户内 RBAC（资源/行/列权限）+ Owner 规则；租户上下文仅通过 `X-Tenant-Id` 传递，**租户侧接口 URL 不包含 tenant_id**。

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
    └── __init__.py
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

> 说明：本表仅列出关键路径；完整清单以 `tech.md` 为准。

| 方法   | 路径                                                                       | 说明                                  | View（views\_\*.py）                             | Serializer                      | Service（函数）                                 | 权限                                 |
| ------ | -------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------ | ------------------------------- | ----------------------------------------------- | ------------------------------------ |
| GET    | `/api/roles`                                                               | 角色列表                              | `views_roles.RoleListView`                       | `RoleSerializer`                | `role_service.list_roles()`                     | TENANT_SETTINGS:VIEW/EDIT            |
| POST   | `/api/roles`                                                               | 创建角色                              | `views_roles.RoleCreateView`                     | `RoleCreateSerializer`          | `role_service.create_role()`                    | TENANT_SETTINGS:MANAGE               |
| PATCH  | `/api/roles/{role_id}`                                                     | 编辑角色                              | `views_roles.RoleUpdateView`                     | `RoleUpdateSerializer`          | `role_service.update_role()`                    | TENANT_SETTINGS:MANAGE               |
| DELETE | `/api/roles/{role_id}`                                                     | 删除角色                              | `views_roles.RoleDeleteView`                     | `EmptySerializer`               | `role_service.delete_role()`                    | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/roles/{role_id}/resource-permissions`                                | 读取角色资源权限（按 scope）          | `views_role_permissions.RoleResourcePermGetView` | `RoleResourcePermSerializer`    | `permission_service.get_role_resource_perms()`  | TENANT_SETTINGS:MANAGE               |
| PUT    | `/api/roles/{role_id}/resource-permissions`                                | 覆盖更新角色资源权限（按 scope）      | `views_role_permissions.RoleResourcePermPutView` | `RoleResourcePermPutSerializer` | `permission_service.set_role_resource_perms()`  | TENANT_SETTINGS:MANAGE               |
| GET    | `/api/tables/{table_id}/column-permissions`                                | 读取列权限（role_id 维度）            | `views_column_perms.ColumnPermGetView`           | `ColumnPermSerializer`          | `permission_service.get_column_perms()`         | TABLE:MANAGE                         |
| PUT    | `/api/tables/{table_id}/column-permissions`                                | 覆盖更新列权限（role_id 维度）        | `views_column_perms.ColumnPermPutView`           | `ColumnPermPutSerializer`       | `permission_service.set_column_perms()`         | TABLE:MANAGE                         |
| GET    | `/api/tables/{table_id}/row-permissions`                                   | 读取行权限（role_id 维度）            | `views_row_perms.RowPermListView`                | `RowPermSerializer`             | `permission_service.list_row_perms()`           | TABLE:MANAGE                         |
| POST   | `/api/tables/{table_id}/row-permissions`                                   | 创建行权限（FilterDSL）               | `views_row_perms.RowPermCreateView`              | `RowPermCreateSerializer`       | `permission_service.create_row_perm()`          | TABLE:MANAGE                         |
| PATCH  | `/api/tables/{table_id}/row-permissions/{row_perm_id}`                     | 编辑行权限                            | `views_row_perms.RowPermUpdateView`              | `RowPermUpdateSerializer`       | `permission_service.update_row_perm()`          | TABLE:MANAGE                         |
| DELETE | `/api/tables/{table_id}/row-permissions/{row_perm_id}`                     | 删除行权限                            | `views_row_perms.RowPermDeleteView`              | `EmptySerializer`               | `permission_service.delete_row_perm()`          | TABLE:MANAGE                         |
| POST   | `/api/users/{tenant_user_id}/roles`                                        | 给成员授予角色                        | `views_membership.UserRoleGrantView`             | `UserRoleGrantSerializer`       | `membership_service.grant_roles()`              | TENANT_SETTINGS:MANAGE               |
| DELETE | `/api/users/{tenant_user_id}/roles/{role_id}`                              | 撤销成员角色                          | `views_membership.UserRoleRevokeView`            | `EmptySerializer`               | `membership_service.revoke_role()`              | TENANT_SETTINGS:MANAGE               |
| POST   | `/api/users/{tenant_user_id}/owner`                                        | 设为租户 Owner（转移所有权）          | `views_membership.SetOwnerView`                  | `EmptySerializer`               | `membership_service.set_owner()`                | TENANT_SETTINGS:MANAGE（owner-only） |
| DELETE | `/api/users/{tenant_user_id}/owner`                                        | 取消 Owner                            | `views_membership.UnsetOwnerView`                | `EmptySerializer`               | `membership_service.unset_owner()`              | TENANT_SETTINGS:MANAGE（owner-only） |

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
    └── __init__.py
```

## 模型（与 tech.md 数据表对齐）

| 文件             | 模型               | db_table             | 说明                                                                   |
| ---------------- | ------------------ | -------------------- | ---------------------------------------------------------------------- |
| `models/node.py` | `ResourceTreeNode` | `resource_tree_node` | scope 分树；节点类型 FOLDER/ASSET；维护 parent/排序/路径（可选缓存）。 |

## Services（用例层：写操作）

- `services.py`
  - `list_children(scope, parent_node_id)`：按 scope 获取子节点（过滤 NONE 权限）
  - `create_folder(scope, parent_node_id, name)`
  - `update_node(scope, node_id, name/parent/order)`
  - `move_nodes(scope, moves[])`
  - `reorder(scope, parent_node_id, ordered_ids[])`
  - `delete_node(scope, node_id)`：空文件夹校验或递归删除策略（按产品决策）

## API（接口清单与代码落点）

| 方法   | 路径                                             | 说明                                   | View（views\_\*.py）          | Serializer               | Service（函数）                | 权限                    |
| ------ | ------------------------------------------------ | -------------------------------------- | ----------------------------- | ------------------------ | ------------------------------ | ----------------------- |
| GET    | `/api/resource-trees/{scope}/children`           | 获取 scope 下 children（node_id 可选） | `views_tree.ChildrenView`     | `TreeChildrenSerializer` | `tree_service.list_children()` | 资源可见（NONE 不可见） |
| POST   | `/api/resource-trees/{scope}/folders`            | 创建文件夹                             | `views_tree.FolderCreateView` | `FolderCreateSerializer` | `tree_service.create_folder()` | 对应 scope:EDIT         |
| POST   | `/api/resource-trees/{scope}/move`               | 移动节点（跨父节点）                   | `views_tree.MoveView`         | `MoveSerializer`         | `tree_service.move_nodes()`    | 对应 scope:EDIT         |
| PATCH  | `/api/resource-trees/{scope}/nodes/{node_id}`    | 重命名/移动前置校验用字段更新          | `views_tree.NodeUpdateView`   | `NodeUpdateSerializer`   | `tree_service.update_node()`   | 对应 scope:EDIT         |
| DELETE | `/api/resource-trees/{scope}/nodes/{node_id}`    | 删除节点/目录                          | `views_tree.NodeDeleteView`   | `EmptySerializer`        | `tree_service.delete_node()`   | 对应 scope:MANAGE       |
| POST   | `/api/resource-trees/{scope}/reorder`            | 同层排序调整                           | `views_tree.ReorderView`      | `ReorderSerializer`      | `tree_service.reorder()`       | 对应 scope:EDIT         |

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
    └── __init__.py
```

## Services（用例层：写操作）

- `services/tables.py`
  - `list_tables()` / `create_table()` / `get_table()` / `update_table()` / `delete_table()`
  - 联动：DW DDL（`integrations.dw.ddl`）+ 资源树节点（scope=TABLE）+ 审计
- `services/fields.py`
  - `list_fields()` / `create_field()` / `update_field()` / `delete_field()` / `reorder_fields()`
- `services/records.py`
  - `create_record()` / `get_record()` / `update_record()` / `delete_record()` / `batch_delete()`
  - `query_records()`：调用 QueryEngine（FilterDSL + 排序分页 + 行列权限）

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
├── services.py               # validate/run/export（供 api/query/* 与 modeling/reports 复用）
└── api/
    ├── __init__.py
    ├── serializers.py
    ├── views_query.py
    └── urls.py
```

## Services（用例层：写操作）

- `services.py`
  - `validate()`：校验 FilterDSL / QueryConfig
  - `run()`：编译 SQL + 注入权限约束 + 执行（`integrations.dw.client`）
  - `export_csv()`：创建 ExportJob（`reports.export_job`）并提交执行任务

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

---

# reports ｜报表链路

**模块定位**：Dataset（物化表）→ Chart → Dashboard；支持 refresh_run 与 export_job。

> 说明：`Dashboard.render` 标注为 **内部/实验**；不要作为稳定对外 API 的唯一实现依赖。

## 目录结构

```text
src/apps/reports/
├── __init__.py
├── apps.py
├── models/
│   ├── __init__.py
│   ├── dataset.py
│   ├── dataset_refresh_run.py
│   ├── chart.py
│   ├── dashboard.py
│   ├── dashboard_item.py
│   └── export_job.py
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
    └── __init__.py
```

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
│   ├── flow.py
│   ├── node.py
│   ├── edge.py
│   ├── run.py
│   ├── node_run.py
│   └── run_log.py
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
    └── __init__.py
```

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
│   └── notification.py
├── selectors.py
├── services.py
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── views_notifications.py
│   └── urls.py
├── migrations/
└── tests/
    └── __init__.py
```

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
│   └── audit_log.py
├── selectors.py
├── services/
│   ├── __init__.py
│   ├── audit.py
│   └── meta.py
├── api/
│   ├── __init__.py
│   ├── serializers.py
│   ├── permissions.py
│   ├── views_audit.py
│   ├── views_meta.py
│   └── urls.py
├── migrations/
└── tests/
    └── __init__.py
```

---

# platform_admin ｜平台后台

**模块定位**：平台管理员 API：GlobalUser/Tenant/TenantUser 管理（/admin/api/*）与平台审计（/api/platform/audit-logs*）。

## 目录结构

```text
src/apps/platform_admin/
├── __init__.py
├── apps.py
├── services/
│   ├── __init__.py
│   ├── users.py
│   ├── tenants.py
│   ├── tenant_users.py
│   └── platform_audit.py
├── api/
│   ├── __init__.py
│   ├── serializers_users.py
│   ├── serializers_tenants.py
│   ├── serializers_tenant_users.py
│   ├── serializers_platform_audit.py
│   ├── permissions.py
│   ├── views_users.py
│   ├── views_tenants.py
│   ├── views_tenant_users.py
│   ├── views_platform_audit.py
│   └── urls.py
└── tests/
    └── __init__.py
```

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

---

## 4. 实施清单（落地步骤）

1. 按上述目录创建包与空文件；确保 `config/settings/base.py` 正确装载 `INSTALLED_APPS`。
2. 先实现 `accounts`（登录/刷新/退出 + TenantContext 注入）。
3. 实现 `iam` 的 PermissionEngine 与 FilterDSL 编译（`common.dsl` → SQL）。
4. 实现 `resource_tree`（scope 分树）与 `modeling`（表/字段 + DW DDL）。
5. 实现 `query_engine`（validate/run/export）并在 `modeling/reports` 复用。
6. 实现 `execution`（TaskRunInstance + dispatcher + worker handler 注册）。
7. 实现 `reports`（dataset_refresh_run + export_job + worker）。
8. 实现 `flows`（graph 校验 + schedule + run/node_run/log）。
9. 实现 `audit_logs` 与 `platform_admin`，补齐平台侧接口组与审计 meta 接口。
10. **测试落地**：模块内补齐单测（`apps/*/tests/`），顶层补齐集成冒烟（`src/tests/*`）。

> 备注：如发现 tech.md 中新增/调整接口或表字段，应以 tech.md 为准更新本文件；禁止“实现少做”。
