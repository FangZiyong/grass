下面是一份**整合了你前面技术架构 + PRD + 我刚才那批补丁决策**的「统一技术文档」。

* 目录结构：严格按你 PRD 的一级目录（0–10）对齐。
* 每一节都站在「两个初级开发照着写能写出一模一样的系统」的标准上，把关键标准和边界条件说死。
* 有些已经在 PRD 里讲得很清楚的纯业务描述，我不再重复，只补上**技术实现/约束**，否则长度会爆炸。

---

# 0. 文档信息（技术版）

## 0.1 文档范围与读者

* 面向对象：

  * 后端开发（Django + DRF）
  * 前端开发（Vue3 + Vben）
* 目标：

  * 两个初级开发在不互相沟通的情况下，**只看本技术文档 + PRD，就能实现功能且行为一致**。
* 依赖前置：

  * 你提供的技术栈与架构图是本技术文档的前提，不再赘述。

## 0.2 环境与基础设施

* 后端：

  * Python 3.10+
  * Django 4.x
  * DRF
  * MySQL 8.0+
  * Redis：缓存 + Celery broker
  * Celery + Celery Beat
  * 本地 LLM：`ollama`（HTTP 调用）
* 前端：

  * Vue3 + Vite
  * Vben Admin（Ant Design Vue）
  * Pinia, Vue Router, Axios, ECharts, AntV X6

## 0.3 全局统一约定（非常重要）

### 0.3.1 ID 规范（后端 & 前端统一）

* **数据库层**

  * 所有业务主键用 `BIGINT AUTO_INCREMENT` 或 `UUID`（二选一，看具体表）。
  * 文档默认假定 BIGINT；如有 UUID，会特别指出。
* **API 层**

  * **所有返回给前端的 id 字段，类型一律为字符串**（避免 JS 精度问题），值等于数据库主键的字符串表示：

    * 例：数据库 `id = 10` → 返回 `"id": "10"`.
  * 不在 `id` 里拼接类型前缀（如 `table_1`），**类型统一用 `type` 字段区分**：

    * 例：资源树节点：`{ "id": "10", "type": "TABLE" }`
* **前端**

  * 所有 store / route / 组件内部 ID 也用字符串处理。
  * 如需带前缀（例如 `table_10` 用于组件内部 key），由前端自行拼接。

### 0.3.2 时间与时区

* 存储与 API：

  * **所有时间字段均使用 UTC 时间，格式为 ISO8601 + `Z`**：

    * 示例：`"2025-12-08T01:02:03Z"`.
* 调度（Cron）：

  * V1：**统一使用服务器时区**（例如部署在上海则 `Asia/Shanghai`），不做租户时区差异。
  * 文案上可提示「当前调度时间基于服务器时区」。
* 前端展示：

  * 前端负责本地化展示，可按浏览器时区或租户配置。

### 0.3.3 API 响应格式 & HTTP 状态码

统一响应结构（所有 REST API）：

```json
{
  "success": true,
  "data": { ... },       // 成功时有效
  "error": {             // 失败时有效
    "code": "xxx",
    "message": "人类可读错误信息",
    "details": { ... }   // 可选，字段级错误等
  },
  "trace_id": "uuid"
}
```

HTTP 状态与 `success` 的对应关系（**必须遵守**）：

| 场景             | HTTP Status | success | 示例 error.code                     |
| -------------- | ----------- | ------- | --------------------------------- |
| 正常业务成功         | 200         | true    | -                                 |
| 业务校验失败（参数错误等）  | 400         | false   | `COMMON__VALIDATION_ERROR`        |
| 未认证（无/无效 JWT）  | 401         | false   | `AUTH__UNAUTHORIZED`              |
| 已认证但无权限        | 403         | false   | `AUTH__FORBIDDEN` 或资源相关 code      |
| 资源不存在          | 404         | false   | `COMMON__NOT_FOUND`               |
| 资源冲突（依赖/唯一约束等） | 409         | false   | `MODELING__TABLE_DELETE_CONFLICT` |
| 服务器内部异常        | 500         | false   | `COMMON__INTERNAL_ERROR`          |

**禁止**所有错误统一 200 + `success=false`；务必结合 HTTP 语义。

### 0.3.4 错误码使用约定

* 错误码命名格式：`模块前缀__具体错误名`：

  * 例如：`MODELING__TABLE_DELETE_CONFLICT`、`FLOW__RUN_CONFLICT`。
* 关键场景推荐错误码（摘重点）：

  * 删除表但仍有依赖 → `MODELING__TABLE_DELETE_CONFLICT`（409）
  * 同一 Flow 已有 RUNNING 再次触发 → `FLOW__RUN_CONFLICT`（409）
  * 无表数据权限 → `PERMISSION__TABLE_DATA_FORBIDDEN`（403）
  * DSL 校验失败 → `DSL__INVALID_FILTER`（400）
* 完整错误码表可在实现时维护为常量文件，前后端共同引用。

### 0.3.5 trace_id 规范

* 每个请求都必须附带 `trace_id`：

  * 若请求头中存在 `X-Trace-Id`，后端使用该值；
  * 否则由后端生成新的 UUID（字符串）。
* 响应：

  * Body 中的 `trace_id` 与响应头 `X-Trace-Id` 一致。
* 日志：

  * 后端所有日志（包括审计日志）都应携带 `trace_id` 字段用于链路追踪。

---

# 1. 核心概念与数据实体（技术实现版）

本节对应 PRD 的 1.x，侧重于**数据库结构 + ORM 约束 + 权限计算规则**。

## 1.1 GlobalUser / Tenant / TenantUser

### 1.1.1 GlobalUser（平台用户）

* 表：`platform_global_user`
* 主键：`id` BIGINT
* 核心字段和约束：

  * `login_name`：唯一索引（全局）
  * `email`：可选唯一索引（根据业务需要）
  * `status`：`ACTIVE` / `DISABLED`
* 技术细节：

  * 登录时仅校验 `status=ACTIVE`。
  * 禁用后：

    * 无法获取 JWT；
    * 已有 JWT 不强制失效（V1 不做 token 黑名单）。

### 1.1.2 Tenant（租户）

* 表：`platform_tenant`
* 主键：`id` BIGINT
* 字段：

  * `code`：唯一索引
  * `status`：`ACTIVE` / `SUSPENDED`
* 技术行为：

  * `SUSPENDED` 时：

    * 所有 `TenantUser` 无法访问租户工作区；
    * 调度器在检查 Flow 时，若租户 `SUSPENDED`，不再创建新的 Run。

### 1.1.3 TenantUser（租户用户）

* 表：`platform_tenant_user`
* 主键：`id` BIGINT
* 重要字段：

  * `tenant_id`（FK → Tenant）
  * `user_id`（FK → GlobalUser）
  * `status`：`ACTIVE` / `DISABLED`
  * `is_owner`：bool
* 约束：

  * `(tenant_id, user_id)` 唯一索引。
  * 不在 DB 层强制 “至少一个 owner”，由业务逻辑在创建/禁用时检查。
* 行为：

  * 认证通过后，`tenant_middleware` 会检查：

    * `Tenant.status = ACTIVE`
    * `TenantUser.status = ACTIVE`
    * 否则返回 403。

## 1.2 Role（租户角色）

* 表：`permissions_role`
* 主键：`id` BIGINT
* 字段：

  * `tenant_id`（FK）
  * `name`：同一租户下唯一索引
  * `is_system`：bool（系统内置角色）
* 行为：

  * `is_system = true` 的角色不可删除。
  * 平台管理员**不能**跨租户编辑角色配置（只在租户工作区内配置）。

## 1.3 ResourceTree（资源树）

* 表：`resources_resource_tree`
* 主键：`id` BIGINT
* 字段：

  * `tenant_id`（FK）
  * `type`：`FOLDER` / `TABLE` / `FLOW` / `BOARD`
  * `parent_id`（FK → 自身，可 NULL，表示根节点）
  * `display_name`
  * `sort_order` INT
  * `ref_id` BIGINT：指向实际资源（表/Flow/Board）的主键，**仅当 type != FOLDER 时有效**。
* 根节点设计：

  * 可以有多个根 FOLDER 记录（`parent_id IS NULL`）。
  * 前端不虚构“根目录”节点，直接根据返回列表渲染树。

## 1.4 权限实体

### 1.4.1 RolePermission

* 表：`permissions_role_permission`
* 字段：

  * `tenant_id`
  * `role_id`
  * `resource_type`：`TABLE_SCHEMA` / `TABLE_DATA` / `FLOW` / `BOARD`
  * `resource_id`：可以是 ResourceTree 节点 id（包括 FOLDER/TABLE/FLOW/BOARD）
  * `permission`：`NONE` / `VIEW` / `EDIT` / `MANAGE`
* 约束：

  * 同一 `(tenant_id, role_id, resource_type, resource_id)` 仅保留一条记录。

### 1.4.2 ColumnPermission

* 表：`permissions_column_permission`
* 字段：

  * `tenant_id`
  * `role_id`
  * `table_id`（表元数据 id）
  * `column_code`
  * `access_level`：`HIDDEN` / `READONLY` / `READWRITE`
* 默认行为（**重要**）：

  * 未配置的列默认 `READWRITE`，仅受资源级 TABLE_DATA 权限控制。

### 1.4.3 RowPermission

* 表：`permissions_row_permission`
* 字段：

  * `tenant_id`
  * `role_id`
  * `table_id`
  * `filter_json`（JSON DSL）
* 合并策略：

  * 对于某一 TenantUser 和某一表：

    * 收集其所有角色的 RowPermission 条目：`rule1, rule2, ...`
    * 最终行过滤 DSL：`rule1 OR rule2 OR ...`
  * 若用户至少一个角色在该表上的 TABLE_DATA 权限为 `MANAGE`：

    * **V1 规则：忽略所有 rowFilter，看全量数据**。

## 1.5 最终权限计算规则（必须统一）

### 1.5.1 单角色的资源级权限

对于指定 `role` + `resource_type` + `资源所在 ResourceTree 节点`：

1. 起始权限 = `NONE`。
2. 从根到叶遍历路径上的所有 FOLDER 与叶子节点（TABLE/FLOW/BOARD 自身）：

   * 若在某个 FOLDER 节点有 RolePermission 配置，则：

     * `当前权限 = max(当前权限, folder_permission)`；
   * 若在叶子节点有 RolePermission 配置，则：

     * `当前权限 = max(当前权限, leaf_permission)`；
3. 得到该角色对该资源的最终权限。

**注意：**

* 子节点配置为 `NONE` 并不会降低父节点已经给出的 `VIEW/EDIT` 权限；`NONE` 视为“未配置”。

### 1.5.2 多角色合并

* 对于某个 TenantUser：

  * 找到其在该租户下所有 `role`；
  * 对同一资源：

    * 先按上面步骤算出每个角色的权限；
    * 最终权限 = 所有角色权限的最大值（MANAGE > EDIT > VIEW > NONE）。

### 1.5.3 列权限 & 行权限应用顺序

对于某个表数据查询请求：

1. 计算该用户 TABLE_DATA 权限：

   * 若 `< VIEW` → 403。
2. 若 TABLE_DATA = MANAGE：

   * 跳过 RowPermission（全量行）。
3. 否则：

   * 构造 `row_permission_filter`（OR 合并各角色规则）。
4. 列权限：

   * 收集该用户所有角色 ColumnPermission；
   * 对每列：

     * 若所有角色都为 HIDDEN → 不在 SELECT 列表中返回；
     * 若存在至少一条 READWRITE → 可写；
     * 否则若存在 READONLY → 只读。
5. 最终查询过滤条件：

   * `final_filter = AND(dataset_base_filter, widget_filter, row_permission_filter)`（缺失的部分省略）。

---

# 2. 统一过滤条件 JSON DSL（技术实现细则）

本节基于 PRD 的 DSL 结构，补充**类型校验 + SQL 生成规则 + 特殊变量处理**。

## 2.1 DSL 结构回顾

* 条件组：

```json
{
  "op": "and",
  "conditions": [ { ... }, { ... } ]
}
```

* 简单条件：

```json
{
  "field": "amount",
  "operator": ">",
  "value": 100
}
```

支持的 `operator` 与 PRD 一致。

## 2.2 类型检查与字段元数据

* 在构造 SQL 前，必须通过表元数据获取字段定义（data_type）：

  * `string`, `text`, `int`, `bigint`, `float`, `decimal`, `bool`, `date`, `datetime` 等。
* 校验：

  * 对 number/operator：

    * `> >= < <= between`：字段类型必须为数值或日期/时间类型；
  * 对 `in, not_in`：

    * `value` 必须为数组；
  * 对 `is_null, is_not_null`：

    * 不读取 `value` 字段；
  * 对文本运算（contains 等）：

    * 字段类型必须为 string/text。
* 类型不匹配 → 返回 400，错误码：`DSL__INVALID_FILTER`。

## 2.3 特殊变量处理

* 支持以下特殊值（字符串）：

| 变量名                | 替换为                                         |
| ------------------ | ------------------------------------------- |
| `CURRENT_USER`     | 当前 `TenantUser.id`（数字，参与 `=`、`in` 等）        |
| `CURRENT_DATE`     | 当前日期（UTC）`YYYY-MM-DD`                       |
| `CURRENT_DATETIME` | 当前时间（UTC）ISO8601 字符串或 `YYYY-MM-DD HH:mm:ss` |

* 替换规则：

  * 在解析 DSL 时，遇到 `value` 是上述字符串常量时替换为具体值。

## 2.4 SQL 生成规则（与 sql_builder 结合）

* 输入：

  * 表元数据（表名、字段列表、字段类型）
  * `final_filter` DSL
* 递归生成：

  * 条件组：

    * `op = "and"` → `(... AND ...)`
    * `op = "or"` → `(... OR ...)`
  * 简单条件：

    * 统一使用参数化 SQL（占位符）：

      * 例如：`field = %s`。
* 常见 operator 映射：

| operator      | SQL 示例                            |
| ------------- | --------------------------------- |
| `=`           | `field = %s`                      |
| `!=`          | `field <> %s`                     |
| `>` / `<`…    | `field > %s` 等                    |
| `in`          | `field IN (%s, %s, ...)`          |
| `not_in`      | `field NOT IN (...)`              |
| `between`     | `field BETWEEN %s AND %s`         |
| `contains`    | `field LIKE CONCAT('%', %s, '%')` |
| `starts_with` | `field LIKE CONCAT(%s, '%')`      |
| `ends_with`   | `field LIKE CONCAT('%', %s)`      |
| `is_null`     | `field IS NULL`                   |
| `is_not_null` | `field IS NOT NULL`               |

* 空 DSL（条件为 `null` 或无 `conditions`）：

  * 视为不加任何 WHERE 子句（除了 tenant_id 强制条件）。

---

# 3. 平台后台（Platform Admin Console）技术设计

本节对应 PRD 3.x，重点定义**API、权限控制、查询规则**。
平台后台只能由拥有「平台管理员」身份的 GlobalUser 使用（可在 GlobalUser 中用 `is_staff` 标记）。

## 3.1 认证 & 权限

* 所有 `/api/admin/**` 接口：

  * 必须有有效 JWT；
  * `request.user.is_staff = True` 且非禁用；
  * 否则返回 403。

## 3.2 GlobalUser 管理

### 3.2.1 列表 API

* `GET /api/admin/users`
* 查询参数：

  * `q`（可选）：模糊搜索 login_name / display_name / email
  * `status`（可选）：`ACTIVE` / `DISABLED`
  * 分页：`page`, `page_size`
* 行为：

  * 按创建时间倒序；
  * 返回统一分页结构：`total`, `items`.

### 3.2.2 创建 / 编辑 / 启用禁用

* 创建：

  * `POST /api/admin/users`
  * Body 对应字段：

    * `login_name`, `display_name`, `email`, `password` 等
  * 约束：

    * `login_name` 唯一，否则 400 + `COMMON__VALIDATION_ERROR`.
* 编辑：

  * `PUT /api/admin/users/{id}`
  * `login_name` 禁止修改。
* 启用/禁用：

  * `POST /api/admin/users/{id}/status`
  * Body：`{ "status": "ACTIVE" }` 或 `"DISABLED"`。

## 3.3 Tenant 管理

同 PRD 描述，补充几个技术点：

* `GET /api/admin/tenants`：

  * 支持按 `code`, `status` 过滤。
* `POST /api/admin/tenants`：

  * 新建时 `code` 唯一。
* 状态变更为 `SUSPENDED` 时：

  * 不自动踢出所有在线用户，会在下次请求时阻止访问；
  * 调度器在下一轮检查中也会停发任务。

## 3.4 TenantUser 平台视角管理

* 平台管理员操作接口：

  * 列表：`GET /api/admin/tenants/{tenant_id}/users`
  * 新增成员：`POST /api/admin/tenants/{tenant_id}/users`

    * Body：选已有 GlobalUser 的 id，是否 owner。
  * 修改状态：

    * `POST /api/admin/tenant_users/{id}/status`。
* 平台管理员**不直接配置角色/权限**：

  * 仅能将 GlobalUser 加入/移出租户、设置 owner、启用/禁用。

---

# 4. 租户工作区总览（认证、租户上下文、DRF 权限）

本节对应 PRD 4.x + 5 开头的基础，决定所有后面的行为。

## 4.1 JWT 认证实现

### 4.1.1 JWT Payload 标准格式

* Access Token payload 示例：

```json
{
  "sub": "1",                // GlobalUser.id
  "login_name": "alice",
  "display_name": "Alice",
  "exp": 1733600000
}
```

* 不在 Token 中保存任何租户信息（tenant_id/role 等）——**统一从 DB 查询**。

### 4.1.2 登录 API

* `POST /api/auth/login`
* Body：

```json
{
  "login_name": "alice",
  "password": "******"
}
```

* 响应：

```json
{
  "success": true,
  "data": {
    "access_token": "xxx",
    "refresh_token": "yyy",
    "user": {
      "id": "1",
      "login_name": "alice",
      "display_name": "Alice",
      "email": "a@example.com"
    },
    "tenants": [
      { "id": "10", "code": "t_foo", "name": "Foo Corp" }
    ]
  },
  "error": null,
  "trace_id": "..."
}
```

### 4.1.3 Refresh Token 策略（V1 简化）

* V1：**Refresh Token 纯无状态**：

  * 不在服务器保存 refresh token 或 jti；
  * 不实现黑名单；
  * 登出只是前端删除 token。
* 刷新接口：

  * `POST /api/auth/refresh`
  * Body：`{ "refresh_token": "yyy" }`
  * 校验签名 + `exp`；若通过生成新的 `access_token`，可选择旋转 `refresh_token` 或沿用。
* 未来若需要黑名单/吊销，再追加一版设计。

## 4.2 租户中间件 & TenantManager

### 4.2.1 X-Tenant-ID 规范

* 前端在所有**业务请求**中必须携带：

```http
Authorization: Bearer <access_token>
X-Tenant-ID: <tenant_id>   # 字符串形式的租户主键
```

* V1：**只从 Header 获取 tenant_id**，不从 JWT payload 解析。

### 4.2.2 Django 中间件实现规范

中间件顺序示意（简化）：

1. `AuthMiddleware`（自定义 DRF Authentication 或 JWT 中间件）
2. `TenantMiddleware`

`TenantMiddleware` 行为：

1. 从 Header 读取 `X-Tenant-ID`，

   * 若缺失：

     * 若访问的是平台后台接口 `/api/admin/**`，可忽略；
     * 若访问租户业务接口 `/api/app/**`，返回 400 + `COMMON__VALIDATION_ERROR`。
2. 验证该 `tenant_id` 是否存在且 `status=ACTIVE`；
3. 根据 `request.user` 和 `tenant_id` 查找 `TenantUser`：

   * 若不存在 / 不 ACTIVE → 403。
4. 把以下信息写入：

   * `request.tenant`
   * `request.tenant_user`
   * 设置 `contextvar tenant_id`。

### 4.2.3 TenantManager / TenantQuerySet 的实现约束

* 使用 `contextvars.ContextVar` 存当前 `tenant_id`，禁止使用 thread local。
* 所有需要租户隔离的模型继承 `TenantBaseModel`：

```python
class TenantBaseModel(BaseModel):
    tenant = models.ForeignKey("platform.Tenant", on_delete=models.CASCADE)

    objects = TenantManager()
```

* `TenantManager.get_queryset()` 必须强制：

```python
tenant_id = tenant_contextvar.get(None)
if tenant_id is None:
    raise RuntimeError("Tenant not set")
return super().get_queryset().filter(tenant_id=tenant_id)
```

* 禁止在业务代码里使用 `_base_manager` 绕开租户过滤。

## 4.3 DRF 权限类 & PermissionService

* 统一接口（`permissions.services.PermissionService`）：

  * `get_resource_permission(tenant_user, resource_type, resource_id) -> PermissionEnum`
  * `get_table_column_permissions(tenant_user, table) -> Dict[column_code, ColumnAccessEnum]`
  * `get_table_row_filter(tenant_user, table) -> dsl or None`
* 每个业务模块实现自己的 DRF Permission 类：

  * 例如 `ModelingTablePermission` 从 URL 中取 `table_id`，调用上述接口。
* **V1 不强制使用 Redis 做权限缓存**：

  * 若要优化，可在 Service 内部使用进程内 LRU 缓存（一请求生存期）。

---

# 5. 租户前台：权限与设置（Settings）

对应 PRD 5.x，补充技术细节。

## 5.1 租户用户管理（Settings → Users）

### 5.1.1 API

* 列表：`GET /api/app/settings/users`

  * 仅 TenantOwner 或具备特定管理权限的角色可访问。
* 编辑用户角色：

  * `PUT /api/app/settings/users/{tenant_user_id}/roles`
  * Body：`{ "role_ids": ["1", "2"] }`，覆盖原有角色绑定。
  * 删除角色时需保证至少有一个 TenantUser 拥有 `is_owner`，但不强制必须有某个特定 role。

## 5.2 角色管理（Settings → Roles）

### 5.2.1 API

* 列表：`GET /api/app/settings/roles`
* 创建：`POST /api/app/settings/roles`
* 编辑：`PUT /api/app/settings/roles/{id}`
* 删除：`DELETE /api/app/settings/roles/{id}`

  * 若 `is_system = true` → 403。

## 5.3 角色权限配置

### 5.3.1 ResourceTree + RolePermission

* 接口：

  * 查询角色权限：

    * `GET /api/app/settings/roles/{id}/permissions`
  * 保存角色权限：

    * `PUT /api/app/settings/roles/{id}/permissions`
    * Body：包含三类资源树（表/Flow/Board）节点上的权限配置列表。
* 实现要点：

  * 前端可只传显式配置项，后端负责插入/更新/删除对应 RolePermission。

## 5.4 列权限 / 行权限配置

* 列权限接口：

  * `GET /api/app/modeling/tables/{table_id}/column_permissions?role_id=xxx`
  * `PUT /api/app/modeling/tables/{table_id}/column_permissions`
* 行权限接口：

  * `GET /api/app/modeling/tables/{table_id}/row_permissions?role_id=xxx`
  * `PUT /api/app/modeling/tables/{table_id}/row_permissions`
* 保存行权限时：

  * 后端必须对 `filter_json` 进行 DSL 校验；
  * 校验失败 → 400 + `DSL__INVALID_FILTER`.

---

# 6. 建模模块（Modeling）技术细则

对应 PRD 6.x，这一节比较核心。

## 6.1 元数据模型与物理表命名

### 6.1.1 元数据表

* 表元数据：`modeling_table`

  * 字段：`id`, `tenant_id`, `code`, `display_name`, `type`, `description`, ...
* 字段元数据：`modeling_field`

  * 字段：`id`, `tenant_id`, `table_id`, `code`, `display_name`, `data_type`, `is_primary`, `is_required`, `default_value`, `is_internal`, `description`.

### 6.1.2 物理表命名规则（硬性统一）

* 物理表名：`biz_{tenantId}_{tableCode}`

  * 全小写；
  * `tenantId` 为数字主键的十进制字符串，不补零；
  * 例：租户 10 的 `order` 表 → `biz_10_order`。
* 物理表结构：

  * 系统字段：

    * `id` BIGINT PK AUTO_INCREMENT
    * `tenant_id` BIGINT（冗余；也用于行级强隔离）
    * 可选审计字段：`created_at`, `updated_at`, `created_by`, `updated_by`.
  * 业务字段：

    * 从 `modeling_field` 同步维护。

### 6.1.3 主键语义

* 物理主键：

  * 永远是系统字段 `id`。
* `is_primary`：

  * 只是业务层含义（业务主键标记），V1 **不在 DB 层建额外 PK/UNIQUE 约束**。

## 6.2 字段类型映射表（统一）

| data_type (元数据) | MySQL 列类型      | 说明              |
| --------------- | -------------- | --------------- |
| string          | VARCHAR(255)   | 默认              |
| text            | TEXT           | 长文本             |
| int             | INT            |                 |
| bigint          | BIGINT         |                 |
| float           | DOUBLE         |                 |
| decimal         | DECIMAL(18, 4) | 金额等             |
| bool            | TINYINT(1)     | 0/1             |
| date            | DATE           |                 |
| datetime        | DATETIME(6)    | 存 UTC 时间        |
| json            | JSON           | MySQL 8 原生 JSON |

后续如需扩展类型，必须更新此映射表，并同步前端字段类型列表。

## 6.3 表创建 / 修改 / 删除

### 6.3.1 新建表流程（后端）

1. 校验：display_name、code 唯一性等。
2. 根据物理表命名规则，检查 MySQL 中是否已有同名表。
3. 事务执行：

   * 插入 `modeling_table` 记录；
   * 默认创建系统字段元数据（如 `id`, `tenant_id`, `created_at` 等，`is_internal=true`）；
   * 执行 `CREATE TABLE ...`，包含系统字段和租户字段；
   * 在 ResourceTree 中创建 `TABLE` 类型的节点。
4. 若任一步失败，回滚事务。

### 6.3.2 字段新增

1. 校验表存在并在当前租户下。
2. 根据 data_type 决定 MySQL 类型。
3. 校验：

   * 若 `is_required = true` 且无 `default_value`：

     * 若是新增字段，物理层可允许 NULL，由业务层保证插入/更新时非空；
     * V1 不执行 NOT NULL 约束。
4. 事务执行：

   * 在 `modeling_field` 中插入记录；
   * 对物理表执行 `ALTER TABLE biz_{tenantId}_{tableCode} ADD COLUMN ...`（允许 NULL）。
5. 失败则回滚。

### 6.3.3 字段修改

* 允许修改：

  * `display_name`, `is_required`, `default_value`, `description`.
* 不允许修改：

  * `code`, `data_type`, `is_internal`.
* 实现：

  * 不 ALTER TABLE 结构，仅更新元数据。
  * `is_required` 仅用于 API 校验，不改物理列 NULL/NOT NULL。

### 6.3.4 字段删除

1. 校验是否是系统字段：

   * `is_internal=true` → 禁止删除。
2. 依赖检查（至少包括）：

   * Relation 是否引用该字段；
   * Flow 节点配置中是否引用该字段；
   * Dataset / Widget query_config 中是否引用该字段；
   * RowPermission / ColumnPermission 是否引用该字段。
3. 若存在任何依赖：

   * 返回 409 + `MODELING__FIELD_DELETE_CONFLICT`，并列出引用来源。
4. 否则：

   * 事务中：

     * 从 `modeling_field` 删除记录；
     * 物理表 `ALTER TABLE DROP COLUMN`；
   * 失败则回滚。

### 6.3.5 删除表

* 依赖检查范围（V1 须检查的最小集合）：

  * Flow 节点中作为 Source/Sink 表；
  * Dataset 中 `绑定表` 为该表；
  * Widget 中使用该 Dataset（间接依赖）；
  * Relation 中引用该表；
  * RowPermission / ColumnPermission 绑定该表。
* 若存在依赖：

  * 409 + `MODELING__TABLE_DELETE_CONFLICT` + 具体验证列表。
* 否则：

  * 事务中：

    * 删除 `modeling_field`、`modeling_table` 元数据；
    * 删除对应 ResourceTree 节点；
    * 物理层 `DROP TABLE biz_{tenantId}_{tableCode}`。

## 6.4 表数据 CRUD

### 6.4.1 查询

* API：`POST /api/app/modeling/tables/{table_id}/data/query`
* Body：

  * 简化查询参数（字段过滤 / 排序 / 分页），或直接 DSL。
* 逻辑步骤：

  1. 通过 PermissionService 计算 TABLE_DATA 权限：

     * `< VIEW` → 403。
  2. 获取列权限：

     * 确定可见列列表。
  3. 获取 rowFilter（如需）。
  4. 合并 Dataset/Widget filter（如果经由 Dataset），否则只用 rowFilter。
  5. 调用 `sql_builder.build_select_query`：

     * 强制添加 `tenant_id = 当前 tenant`；
     * 组合 WHERE 条件；
     * 加入分页与排序。
  6. 返回数据，格式约定见第 8.5 小节。

### 6.4.2 插入 / 更新 / 删除

* 插入：

  * API：`POST /api/app/modeling/tables/{table_id}/data`
  * 校验：

    * TABLE_DATA ≥ EDIT；
    * 所有 `is_required = true` 的字段必须有值（非 NULL）；
    * HIDDEN 列不可写；READONLY 列不可写。
* 更新：

  * API：`PUT /api/app/modeling/tables/{table_id}/data/{id}`
  * 逻辑：

    * 先按 rowFilter + tenant_id + id 查行：

      * 若查不到 → 可视为 404 或 403（推荐 404 避免暴露行存在性）。
    * 检查列权限，仅允许更新 READWRITE 列；
* 删除：

  * API：`DELETE /api/app/modeling/tables/{table_id}/data/{id}`
  * 行为：

    * 同样先按 rowFilter + tenant_id 过滤。
* 并发控制：

  * V1 采用「最后写入覆盖」策略，不做版本号比较；
  * 如后续需要乐观锁，可添加 `version` 字段。

---

# 7. 任务流模块（Flows）技术细则

对应 PRD 7.x。

## 7.1 模型设计

### 7.1.1 Flow

* 表：`flows_flow`
* 字段：

  * `id`, `tenant_id`, `name`, `description`
  * `schedule_type`: `MANUAL` / `CRON`
  * `schedule_cron`: string
  * `schedule_status`: `ENABLED` / `DISABLED`
  * 其它审计字段。

### 7.1.2 FlowNode / FlowEdge

* `flows_flow_node`

  * `id`, `tenant_id`, `flow_id`
  * `type`: `SOURCE_HTTP`, `SOURCE_MYSQL`, `TRANSFORM_FILTER`, `SINK_INTERNAL_TABLE`, ...
  * `name`
  * `config_json`：节点配置 JSON。
* `flows_flow_edge`

  * `id`, `tenant_id`, `flow_id`
  * `from_node_id`, `to_node_id`

### 7.1.3 FlowRun / NodeRun

* `flows_flow_run`

  * `id`, `tenant_id`, `flow_id`
  * `status`: `PENDING` / `RUNNING` / `SUCCESS` / `FAILED`
  * `trigger_type`: `MANUAL` / `SCHEDULED`
  * `config_snapshot`：Flow 配置快照（nodes + edges 的 JSON）
  * `started_at`, `finished_at`, `error_message`
* `flows_node_run`

  * `id`, `tenant_id`, `flow_run_id`, `node_id`
  * `status`, `started_at`, `finished_at`
  * `input_row_count`, `output_row_count`
  * `error_message`

**硬性要求：**
创建 FlowRun 时必须保存 `config_snapshot`，`execute_flow(run_id)` 基于快照执行。后续修改 Flow 不影响历史 Run 的重看。

## 7.2 节点间数据结构（统一）

* 在 Flow 执行引擎内部，节点间的数据统一抽象为：

```python
class DataFrameLike(TypedDict):
    "只做说明，不一定要类定义"
    columns: List[{"name": str, "data_type": str}]
    rows: List[Dict[str, Any]]
```

* 也可以用简单结构：

```python
schema = List[(field_name, data_type)]
rows = List[Dict[str, Any]]
```

* 约定：

  * 所有节点的 `run()` 输入与输出都严格使用该结构；
  * 不在节点之间直接持久化到临时表（V1 面向小中规模数据）。

## 7.3 大数据量限制

* V1：Flow 引擎默认只支持「小中规模」数据：

  * 单节点处理行数上限：例如 100,000（这个值作为常量写在配置里）；
  * 若任何节点的输入或输出行数超过限制：

    * 节点失败，FlowRun 标记 FAILED；
    * 错误码 `FLOW__ROW_LIMIT_EXCEEDED`，提示配置拆分或降采样。

## 7.4 节点类型实现规范（举几个关键）

以 `run(context, input_df) -> output_df` 的伪接口说明，具体框架可自由。

### 7.4.1 Source：HTTP API 源

* config_json 示例（与 PRD 一致）：

  * 包含 URL、Method、Headers、Body、JSONPath、字段映射等。
* 执行：

  1. 按 config 调用 HTTP；
  2. 使用 JSONPath 提取列表；
  3. 按字段映射构造 rows；
  4. 若响应非 2xx 或 JSONPath 结果为空且配置要求非空，节点失败。

### 7.4.2 Transform：Join

**关键边界：列名冲突**：

* 约定：前端在配置时必须为每个输出字段指定 `output_field_name`，并在 UI 上防止冲突。
* 后端验证：

  * 若出现两个不同字段映射到同一 `output_field_name` → 400 + `FLOW__JOIN_FIELD_CONFLICT`。
* 执行：

  * 根据 join_type，相当于 SQL 的 INNER/LEFT JOIN；
  * 基于 input_df 在内存中实现（哈希 join）。

### 7.4.3 Transform：计算字段

* 支持的表达式：

  * 二元运算：`+ - * /`
  * 括号
  * 简单函数：`ABS(x)`, `ROUND(x, n)`, `IF(cond, a, b)` 等固定一个白名单。
* 实现建议：

  * 使用自定义 AST 解析器或安全表达式库；
  * 禁止执行任意 Python 代码。
* 错误：

  * 表达式解析错误 / 运行错误（例如 0 除） → 节点失败。

### 7.4.4 Sink：写入内部表

* 核心规则：

  * 写入前必须验证用户对目标表 `TABLE_DATA ≥ EDIT`；
  * 映射校验：确保所有必填字段有源值。
* 执行：

  * 在一个 DB 事务中完成：

    * 模式 APPEND：直接 insert；
    * 模式 TRUNCATE_INSERT：

      * 先删除 `tenant_id = 当前 tenant` 的所有数据；
      * 再 insert 该 FlowRun 的输出。
  * 任意一行 insert 失败 → 整个事务 rollback → 节点失败。

## 7.5 Flow 执行语义 & 调度

### 7.5.1 单 Flow 同时仅一个 RUNNING

* 创建 FlowRun 时，在事务中检查：

  * 是否存在同一 `flow_id` 下 `status in (PENDING, RUNNING)` 的 Run；
  * 若存在 → 409 + `FLOW__RUN_CONFLICT`。

### 7.5.2 Celery 任务 `execute_flow(run_id)`

执行流程：

1. 将 FlowRun 状态改为 RUNNING，记录 `started_at`。
2. 从 `config_snapshot` 复原 DAG，做拓扑排序，检查无环。
3. 按顺序执行节点：

   * 对每个节点：

     * 创建 NodeRun 记录；
     * 调用对应 NodeExecutor；
     * 记录 input/output 行数；
     * 若失败：

       * NodeRun 标记 FAILED；
       * FlowRun 标记 FAILED，记录 `error_message`；
       * 停止执行后续节点；
       * 退出任务。
4. 全部成功：

   * FlowRun 标记 SUCCESS，记录 `finished_at`。

### 7.5.3 调度器（Scheduler + Celery Beat）

* Celery Beat：

  * 每分钟触发一次任务 `check_scheduled_flows`。
* `check_scheduled_flows`：

  1. 在 DB 查询：

     * `schedule_type = CRON`
     * `schedule_status = ENABLED`
     * 租户状态 ACTIVE
  2. 对每个 Flow，使用 cron 表达式和服务器时区判断是否到期；
  3. 对已到期且当前无 RUNNING Run 的 Flow：

     * 创建 FlowRun（`trigger_type = SCHEDULED`）；
     * 投递 `execute_flow.delay(run_id)`。

---

# 8. 数据集 & 看板模块（Datasets & Boards）

对应 PRD 8.x。

## 8.1 Dataset 技术实现

* 表：`boards_dataset`

  * `id`, `tenant_id`, `name`, `table_id`, `base_filter_json`, `description`
* 权限：

  * Dataset 本身不引入新权限维度：

    * 权限全部沿用绑定表的 TABLE_DATA 权限；
    * 若用户对表无 VIEW 权限 → 不能看到使用该表的数据集。

## 8.2 Board & Widget 模型

* Board：`boards_board`

  * `id`, `tenant_id`, `name`, `description`, `layout_json`（可选全局布局）
* Widget：`boards_widget`

  * `id`, `tenant_id`, `board_id`
  * `type`: `METRIC_CARD` / `CHART` / `TABLE`
  * `title`, `description`
  * `dataset_id`
  * `query_config_json`
  * `viz_config_json`
  * `layout_json`: `{x, y, w, h, zIndex}`

## 8.3 Widget 查询管线（统一规则）

### 8.3.1 Filter 合并顺序

对于 Widget 请求：

1. 找到 Dataset：

   * 校验用户对 Dataset 绑定表的 TABLE_DATA 权限。
2. 获取 Dataset 的 `base_filter` DSL。
3. 解析 Widget 的 `query_config.filter` 为 DSL。
4. 从 PermissionService 获取 `row_permission_filter` DSL（如需）。
5. 合并顺序（**必须一致**）：

```text
final_filter = AND(base_filter, widget_filter, row_permission_filter)
```

* 任何缺失项视为“不过滤”。

### 8.3.2 列权限在 Dataset/Widget 中的应用

* 所有通过 Dataset/Widget 发起的查询：

  * 仍然必须应用 ColumnPermission；
  * 即 SELECT 列表中自动剔除 HIDDEN 列；
  * 如 query_config 中引用了 HIDDEN 列：

    * 保存时校验失败 → 400 + `PERMISSION__COLUMN_FORBIDDEN`。

## 8.4 sql_builder 在看板中的使用

* Widget 调用统一方法：

```python
build_select_query(
    table_meta,
    visible_columns,          # 列权限过滤后的字段
    base_filter_dsl,
    widget_filter_dsl,
    row_permission_dsl,
    tenant_id,
    pagination,               # 对于表格
    order_by,
    group_by,
    aggregations
)
```

* sql_builder 的职责：

  * 组合 WHERE；
  * 生成 GROUP BY + 聚合；
  * 加上 `tenant_id = ?` 固定条件；
  * 返回 SQL + params。

## 8.5 Widget 数据返回格式（统一）

* 所有 `GET /api/app/boards/widgets/{widget_id}/data` 类型接口统一返回：

```json
{
  "success": true,
  "data": {
    "columns": [
      { "field": "date", "data_type": "date" },
      { "field": "total_amount", "data_type": "decimal" }
    ],
    "rows": [
      { "date": "2025-01-01", "total_amount": 1000.0 }
    ]
  },
  "error": null,
  "trace_id": "..."
}
```

* 前端：

  * 图表根据 `columns` 和 `rows` 构造 ECharts option；
  * 表格根据 columns 决定列顺序与渲染。

---

# 9. 本地 LLM（ollama）集成技术细节

对应 PRD 9.x。

## 9.1 模型与调用方式

* V1 建议选择一个确定模型，例如：`llama3.1:8b` 或你实际在 ollama 中部署的模型。
* 统一调用 URL：

  * `http://ollama:11434/api/generate`（示例）
* Timeout 与重试：

  * Timeout 例如 5 秒；
  * 超时或 HTTP 非 2xx 视为失败，不重试（V1 简化）。

## 9.2 Prompt 模板（统一）

### 9.2.1 表编码

Prompt（示例）：

> 你是一个为数据库表生成英文标识符的助手。
> 请将下面的中文表名转换为简短的、全小写、下划线风格的英文标识符。
> 不要输出任何解释或其他文本，只输出标识本身。
> 表名：`{display_name}`

### 9.2.2 字段编码

Prompt（示例）：

> 你是一个为数据库字段生成英文标识符的助手。
> 请结合表的英文编码 `{table_code}`，将下面的中文字段名转换为简短的、全小写、下划线风格的英文标识符。
> 不要输出任何解释或其他文本，只输出标识本身。
> 字段名：`{display_name}`

## 9.3 返回值清洗与 fallback

* 清洗规则：

  1. 全部转小写；
  2. 非 `[a-z0-9_]` 的字符替换为 `_`；
  3. 若首字符不是字母，则添加前缀：

     * 表：`t_`
     * 字段：`f_`
  4. 截断到 50 字符；
  5. 若结果为空或全是 `_`：

     * 视为 LLM 输出无效。
* 唯一性检查：

  * 在当前租户下检查 `code` 是否存在；
  * 若存在：以 `_1`, `_2`, ... 形式递增，直到不冲突。
* fallback：

  * 任一步骤失败 / HTTP 超时 / 清洗后无效：

    * 使用本地规则（例如：对中文做拼音首字母缩写 + 时间戳）；
  * V1 不实现“连续 N 次失败熔断”，每次按上述流程尝试。

## 9.4 前端交互约定

* 表/字段表单中：

  * `display_name` blur 触发一次自动生成；
  * 编码字段为只读；
  * 提供“重新生成”按钮；
* 若接口返回非 200 或 `success=false`：

  * 前端优先使用 fallback 结果；
  * 若连 fallback 也失败（后端会保证给一个），则禁止提交并提示错误。

---

# 10. 非功能要求（安全、多租户、日志、性能）

对应 PRD 10.x。

## 10.1 多租户隔离

* 所有业务表（元数据、权限、Flow、Board 等）必须包含 `tenant_id`。
* ORM 层统一通过 `TenantManager` 强制过滤。
* 物理业务表中也带 `tenant_id`，Select / Insert / Update / Delete 必须显式加上 `tenant_id = ?` 条件。

## 10.2 安全

* 认证：

  * 全站使用 JWT Bearer Token，不使用 Cookie 会话；
  * 所有 `/api/app/**` 和 `/api/admin/**` 均需 JWT。
* CSRF：

  * 因为不用 Cookie，API 可关闭 CSRF 检查。
* XSS：

  * 后端默认不返回富文本 HTML；
  * 前端所有用户输入输出区域统一通过组件转义。
* 敏感信息：

  * 密码使用 Django 自带加密；
  * 外部平台 token/secret 可用对称加密（Fernet）存储在 DB。

## 10.3 审计日志（统一结构）

* 审计表：`common_audit_log`

  * 字段：

    * `id`, `tenant_id`（可为空：平台级）
    * `user_id`（GlobalUser.id）
    * `action`（字符串：`CREATE_TABLE`, `UPDATE_FLOW`, `CHANGE_ROLE_PERMISSION` 等）
    * `object_type`（如：`TABLE`, `FLOW`, `BOARD`）
    * `object_id`（字符串形式主键）
    * `before_snapshot`（JSON，选填）
    * `after_snapshot`（JSON，选填）
    * `created_at`, `trace_id`
* 必须记录的操作（最小集合）：

  * 表/字段/关系的增删改；
  * Flow 配置增删改；
  * FlowRun 执行结果（可简略记录状态变化）；
  * Role/RolePermission/RowPermission/ColumnPermission 变更；
  * Dataset/Board/Widget 增删改。
* 实现：

  * 使用统一 helper 函数 `audit_log(user, action, object_type, object_id, before, after)`。

## 10.4 性能与分页

* 所有列表 API 必须支持分页，并限制 `page_size` 最大值（例如 100）。
* 表数据查询：

  * 最大返回行数：例如 10,000 行；
  * 超出则返回提示使用分页或额外过滤。
* FlowRun 历史：

  * 可按时间归档或定期清理老数据（运维策略）。

---

如果你愿意，下一步我可以按这个技术文档，**挑一个模块（比如 Modeling + LLM 编码）写出完整的 Django 代码骨架**，再一起迭代细节。
