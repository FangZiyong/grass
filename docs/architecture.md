我会在关键地方用「⚠ 注意」标出来你实现时要特别小心的点。

---

# 1. 技术栈选型

## 1.1 后端技术栈

* **框架**：Django 4.x + Django REST Framework (DRF)
* **数据库**：MySQL 8.0+
* **ORM**：Django ORM（自定义多租户 Manager/QuerySet）
* **任务队列**：Celery + Redis（任务流执行 & 调度）
* **缓存**：Redis（权限缓存、资源树缓存、看板查询缓存）
* **LLM 集成**：本地 `ollama`，通过 HTTP 调用
* **文件存储**：本地文件系统或 S3 兼容对象存储
* **认证**：JWT（Bearer Token）

## 1.2 前端技术栈

* **框架**：Vue 3.x
* **UI 框架**：Vben Admin（基于 Ant Design Vue）
* **构建工具**：Vite
* **状态管理**：Pinia
* **路由**：Vue Router
* **HTTP 客户端**：Axios
* **可视化**：ECharts
* **DAG 编辑器**：AntV X6 或自定义封装

## 1.3 开发工具 & 规范

* **版本控制**：Git
* **代码规范**：

  * 后端：Black、isort、flake8
  * 前端：ESLint + Prettier
* **API 文档**：drf-spectacular（OpenAPI 3.0）
* **测试**：

  * 后端：pytest + Django test
  * 前端：Vitest + Vue Test Utils

---

# 2. 系统整体架构

## 2.1 分层架构

```text
┌───────────────────────────────────────────────────────────┐
│                       前端层 (Vue3 + Vben)                │
│  - 平台后台（Platform Admin）                             │
│  - 租户工作区（Modeling / Flows / Boards / Settings）     │
└───────────────────────────────────────────────────────────┘
                              │ HTTP (REST + JWT)
                              ▼
┌───────────────────────────────────────────────────────────┐
│                    API 层 (Django + DRF)                  │
│  - 认证中间件：解析 JWT，注入 request.user                │
│  - 租户中间件：根据 Token/请求信息注入 request.tenant     │
│  - DRF 权限类：针对具体资源做权限检查（调用 PermissionService）│
└───────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                  业务模块 (Django Apps)                   │
│  - platform: 平台后台 (GlobalUser, Tenant, TenantUser)     │
│  - modeling: 表/字段/关系                                  │
│  - flows: 任务流定义与执行                                │
│  - boards: 数据集 + 看板 + Widget                          │
│  - permissions: 角色 & 资源/行/列权限 + PermissionService  │
│  - resources: 资源树 (ResourceTree, FOLDER/TABLE/FLOW/BOARD)│
│  - llm: 调用 ollama 生成编码等                            │
│  - common: BaseModel, 多租户 Manager/QuerySet, 工具        │
└───────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                       数据访问层                          │
│  - Django ORM (带 tenant 过滤的 Manager/QuerySet)         │
│  - dsl_parser + sql_builder（统一 DSL → SQL 出口）          │
└───────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│                      基础设施层                            │
│  - MySQL：元数据 + 业务数据                               │
│  - Redis：缓存 + Celery Broker                            │
│  - 文件存储：本地或对象存储                               │
│  - ollama：本地 LLM 服务                                  │
│  - Celery Worker & Celery Beat (调度)                     │
└───────────────────────────────────────────────────────────┘
```

### ⚠ 注意点

1. **业务权限检查不要放在中间件**：只在中间件里做认证和租户解析，具体资源权限在 DRF 权限类里做。
2. **所有 DSL → SQL 必须走统一 sql_builder**，不要在业务代码里散落 raw SQL。

---

## 2.2 部署架构（JWT 模式）

```text
           ┌───────────────────┐
           │   Nginx 反向代理   │
           │ - 静态资源 (Vue)   │
           │ - /api 转发 Django │
           └─────────┬─────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
   ┌──────▼──────┐       ┌──────▼──────┐
   │ Django 实例1 │       │ Django 实例2 │   ... (水平扩展)
   └──────┬──────┘       └──────┬──────┘
          │                     │
          └──────────┬──────────┘
                     │
              ┌──────▼───────┐
              │   MySQL 主从   │
              └──────┬───────┘
                     │
              ┌──────▼───────┐
              │    Redis     │  (缓存 + Celery Broker)
              └──────┬───────┘
                     │
      ┌──────────────▼──────────────┐
      │      Celery Workers          │
      │  - flow 执行任务              │
      │  - 其他异步任务               │
      └──────────────┬──────────────┘
                     │
              ┌──────▼───────┐
              │  Celery Beat │  (只部署一个，用于调度 Flow)
              └──────────────┘

   ┌──────────────────────────────┐
   │          ollama 服务         │
   │  - 通过 HTTP 调用本地模型     │
   └──────────────────────────────┘
```

### ⚠ 注意点

* Celery Beat **只部署一个实例**，避免多实例重复调度。
* 所有 Django 实例共享同一个 MySQL/Redis 实例集群，保证状态一致。

---

# 3. 后端模块与目录结构设计

## 3.1 后端目录结构（更新版）

```text
backend/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── common/
│   │   ├── models/
│   │   │   ├── base.py        # BaseModel, TenantBaseModel
│   │   │   └── managers.py    # TenantManager, TenantQuerySet
│   │   ├── utils/
│   │   │   ├── dsl_parser.py  # 过滤 DSL 解析
│   │   │   ├── sql_builder.py # SQL 构建器 (统一出口)
│   │   │   └── validators.py
│   │   ├── exceptions.py
│   │   └── permissions.py     # 通用 DRF Permission 基类
│   │
│   ├── platform/
│   │   ├── models/            # GlobalUser, Tenant, TenantUser
│   │   ├── serializers/
│   │   ├── views/
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── resources/             # 资源树模块
│   │   ├── models/            # ResourceTree(FOLDER/TABLE/FLOW/BOARD)
│   │   ├── serializers/
│   │   ├── views/
│   │   └── urls.py
│   │
│   ├── permissions/
│   │   ├── models/            # Role, RolePermission, ColumnPermission, RowPermission
│   │   ├── services.py        # PermissionService (计算最终权限)
│   │   ├── serializers/
│   │   ├── views/             # 角色/权限配置接口
│   │   └── urls.py
│   │
│   ├── modeling/
│   │   ├── models/            # Table, Field, Relation
│   │   ├── serializers/
│   │   ├── views/
│   │   ├── services/          # 表/字段创建、删除等业务逻辑
│   │   ├── permissions.py     # DRF 权限类，调用 PermissionService
│   │   └── urls.py
│   │
│   ├── flows/
│   │   ├── models/            # Flow, Node, Run, NodeRun
│   │   ├── serializers/
│   │   ├── views/
│   │   ├── services/          # Flow 执行引擎 (不含调度)
│   │   ├── nodes/             # Source/Transform/Sink 实现
│   │   ├── scheduler.py       # 调度逻辑（供 Celery Beat 调用）
│   │   └── urls.py
│   │
│   ├── boards/
│   │   ├── models/            # Dataset, Board, Widget
│   │   ├── serializers/
│   │   ├── views/
│   │   ├── services/          # 数据查询服务 (利用 sql_builder)
│   │   └── urls.py
│   │
│   └── llm/
│       ├── services.py        # 调用 ollama, 编码生成, 缓存 & 限流
│       └── urls.py           # 可选：对前端暴露 LLM 服务接口
│
├── middleware/
│   ├── auth_middleware.py     # 解析 JWT，注入 request.user
│   └── tenant_middleware.py   # 解析 tenant_id, 注入 request.tenant / request.tenant_user
│
├── tasks/
│   └── flow_tasks.py          # Celery 任务：execute_flow(run_id)
│
├── requirements.txt
├── manage.py
└── README.md
```

### ⚠ 注意点

* **ResourceTree 独立成一个 app**，避免 modeling/flows/boards 互相硬耦合。
* 权限计算逻辑集中在 `permissions.services.PermissionService`，业务 app 只写“薄”权限类。

---

# 4. 前端目录结构 & 权限实现

## 4.1 前端目录结构（Vue3 + Vben）

与前一版方案大体相同，这里只强调几个重点：

```text
frontend/
├── src/
│   ├── api/
│   │   ├── auth/           # 登录/刷新 JWT
│   │   ├── platform/
│   │   ├── modeling/
│   │   ├── flows/
│   │   ├── boards/
│   │   └── permissions/
│   │
│   ├── composables/
│   │   ├── useAuth.ts      # 获取当前 user, token
│   │   ├── useTenant.ts    # 当前租户信息
│   │   └── usePermission.ts# 基于后端 permission 映射按钮显示
│   │
│   ├── directives/
│   │   └── permission.ts   # v-permission 指令
│   │
│   ├── stores/
│   │   ├── user.ts
│   │   ├── tenant.ts
│   │   └── permission.ts   # 保存后端返回的资源权限快照（用于前端隐藏按钮）
│   │
│   ├── views/
│   │   ├── platform/
│   │   ├── modeling/
│   │   ├── flows/
│   │   ├── boards/
│   │   └── settings/
│   └── ...
└── ...
```

### ⚠ 注意点

* 前端只做“**权限 UI 隐藏**”（比如不显示删除按钮），**真正的权限控制必须在后端 DRF 权限类里做**。
* JWT Token 存在 `localStorage` 或内存（配合刷新 Token），避免放到能被第三方脚本容易盗取的位置（小心 XSS）。

---

# 5. 认证（JWT）与租户隔离 & 权限体系

## 5.1 JWT 认证方案

### 5.1.1 登录流程

1. 用户提交账号密码到 `/api/auth/login`；
2. 后端验证 `GlobalUser`，如需要再检查 `TenantUser` 是否存在 & ACTIVE；
3. 返回：

   * `access_token`（短期有效，比如 30min）
   * `refresh_token`（长期有效，比如 7 天）
   * 当前可访问租户列表（tenant_id + name）
4. 前端保存 token（localStorage/memory）+ 当前选中租户（`X-Tenant-ID` 或路由中带）。

### 5.1.2 请求头格式

```http
Authorization: Bearer <access_token>
X-Tenant-ID: <tenant_id>  # 或从 access_token 中解析
Content-Type: application/json
```

### 5.1.3 Django 侧实现

* 使用 DRF 的自定义 Authentication 类：

  * 解析 Authorization header；
  * 校验 JWT；
  * 找到 `GlobalUser`，set `request.user`；
* 中间件 `tenant_middleware`：

  * 从 Header 中读 `X-Tenant-ID` 或从 Token payload 中解析；
  * 校验当前 user 是否是该租户的 TenantUser；
  * 写入 `request.tenant` 和 `request.tenant_user`。

### ⚠ 注意点

* JWT 模式下，API 路径可以直接**关闭 CSRF 检查**（只对 Cookie-based 会话有用），避免和 DRF Token 冲突。
* 刷新 Token 走独立接口 `/api/auth/refresh`，只允许用 `refresh_token` 换新的 `access_token`。

---

## 5.2 多租户隔离实现

### 5.2.1 ORM 层实现（强制 tenant 过滤）

在 `common.models.managers` 中定义：

* `TenantQuerySet`：

  * 带一个 `for_tenant(tenant_id)` 的方法；
* `TenantManager`：

  * `get_queryset()` 自动附加当前 tenant 过滤（从 thread local 或上下文拿 tenant_id）；

所有需要租户隔离的模型都继承：

```python
class TenantBaseModel(BaseModel):
    tenant = models.ForeignKey("platform.Tenant", on_delete=CASCADE)

    objects = TenantManager()
```

⚠ **要点**：

* 禁止直接使用 `Model._base_manager` 或自建 `objects = models.Manager()` 绕过 `TenantManager`。
* raw SQL 查询必须通过 `sql_builder` 构建，并强制传入 `tenant_id`。

---

## 5.3 权限体系实现

### 5.3.1 PermissionService（统一权限计算服务）

`apps/permissions/services.py` 提供方法：

* `get_resource_permission(tenant_user, resource_type, resource_id)`
  返回 NONE/VIEW/EDIT/MANAGE；
* `get_table_column_permissions(tenant_user, table)`
  返回每列的访问级别：HIDDEN/READONLY/READWRITE；
* `get_table_row_filter(tenant_user, table)`
  返回行权限 DSL（多个角色规则 OR 合并）。

内部逻辑：

1. 根据 `tenant_user` 找到所有 `Role`；
2. 查找 RolePermission + ColumnPermission + RowPermission；
3. 按「最大权限」规则合并；
4. 行权限 DSL 合并成 OR 条件。

### 5.3.2 DRF 权限类

各模块实现自身的 DRF Permission 类，比如：

* `ModelingTablePermission`：

  * 从 URL/path/参数中取 `table_id`；
  * 调用 `PermissionService.get_resource_permission(TABLE_SCHEMA/TABLE_DATA)`；
  * 不满足要求则 raise `PermissionDenied`。
* `FlowPermission` / `BoardPermission` 类似。

### ⚠ 注意点

* **不要在中间件里做具体资源权限判断**，否则需要解析所有 URL，复杂易错。
* PermissionService 可以加 Redis 缓存（key 中包含 `tenant_user_id` + `resource_id`）。

---

# 6. DSL & SQLBuilder（统一数据查询出口）

## 6.1 DSL 结构（与 PRD 保持一致）

统一 JSON 结构，用于：RowPermission、Dataset base_filter、Widget filter、Flow 过滤节点。

* 条件组：

```json
{
  "op": "and",
  "conditions": [
    {...}, {...}
  ]
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

支持：

* op: "and" / "or"
* operator: =, !=, >, >=, <, <=, in, not_in, between, contains, starts_with, ends_with, is_null, is_not_null

---

## 6.2 sql_builder 职责

`common.utils.sql_builder` 提供：

* `build_select_query(table_meta, visible_columns, base_filter_dsl, widget_filter_dsl, row_permission_dsl, tenant_id, pagination, order_by, group_by, aggregations)`

统一职责：

1. 根据 `tenant_id` 生成 `WHERE tenant_id = ?` 条件；
2. 合并：

   * Dataset base_filter；
   * Widget 自身 filter；
   * RowPermission filter；
3. 考虑列权限：

   * 去掉用户不可见字段；
4. 根据 `aggregations` 和 `group_by` 构建 SELECT 子句；
5. 拼出最终 SQL + 参数。

### ⚠ 注意点

* 所有看板查询、Flow 中写入内部表前的 select，都必须通过 sql_builder。
* SQLBuilder 内部要用参数化查询，避免 SQL 注入。

---

# 7. 任务流 & 调度设计（Celery）

## 7.1 任务流执行

* API `POST /api/flows/{flow_id}/run`：

  * 检查：FLOW ≥ EDIT；
  * 检查是否已有 RUNNING 的 Run；
  * 创建 Run 记录（PENDING）；
  * 提交 `flow_tasks.execute_flow.delay(run_id)`；
  * 返回 run_id。

* Celery 任务 `execute_flow(run_id)`：

  * 将 Run 状态置为 RUNNING；
  * 拓扑排序 DAG 节点；
  * 依次执行节点：

    * 每个节点记录 NodeRun（状态/耗时/输入输出行数/错误信息）；
    * 遇到错误：

      * 将 NodeRun 标记 FAILED；
      * 将 Run 标记 FAILED；
      * 整个 Flow 结束；
  * 全部成功：Run 状态置为 SUCCESS。

### ⚠ 注意点

* 同一 Flow 同时只允许一个 RUNNING，避免写入冲突。
* 写入内部表节点使用事务，保证“全成功或全失败”。

---

## 7.2 调度（Scheduler + Celery Beat）

* `flows/scheduler.py` 中实现：

  * `check_scheduled_flows()`：

    * 找出：`schedule_type = CRON` 且 `schedule_status = ENABLED` 的 Flow；
    * 按 cron 表达式判断是否到期；
    * 检查租户状态（非 SUSPENDED）；
    * 检查当前是否有 RUNNING Run；
    * 符合条件则创建 Run + 提交 Celery 任务。

* Celery Beat 配置：

  * 每分钟触发一次 `check_scheduled_flows`。

### ⚠ 注意点

* Celery Beat 只部署一份，不要在 Django 实例里再自己写 while True 的调度脚本。
* 调度逻辑尽量无状态，所有状态依赖 MySQL。

---

# 8. LLM 模块（ollama 集成）

## 8.1 使用场景

* 表编码生成：`generate_table_code(display_name, tenant_id)`
* 字段编码生成：`generate_field_code(display_name, table_code, tenant_id)`

## 8.2 调用方式

* **同步调用**：在 API 内直接调用 ollama（HTTP），避免再绕 Celery 一圈。
* `llm/services.py`：

  * 负责组装 prompt；
  * 发送请求到 `http://ollama:port/api/generate`；
  * 接收结果并清洗编码（小写、蛇形、非法字符替换）。

## 8.3 降级策略

1. LLM 返回后先清洗：

   * 非 `[a-z0-9_]` → `_`；
   * 首字符必须为字母，否则加前缀 `t_` / `f_`；
   * 空或全是 `_` 则判为无效。
2. 若 LLM 调用超时或返回无效：

   * 使用本地编码规则（例如拼音首字母 + 时间戳后缀）；
3. 唯一性校验：

   * 若 `(tenant_id, code)` 已存在，则加 `_1` `_2` 等后缀。

### ⚠ 注意点

* 对同一 `display_name + table_code` 可在内存做简单缓存，减少重复请求；
* 如果某租户连续 N 次 LLM 调用失败，可在短时间内直接使用本地规则（熔断），避免打爆 ollama。

---

# 9. 安全 & 性能优化要点

## 9.1 安全要点

* JWT：

  * Access Token 短有效期；
  * Refresh Token 长期有效，后端可维护黑名单（登出或强制失效）。
* CSRF：

  * 纯 API + JWT 场景，API 路由可以关闭 CSRF 中间件；
* XSS：

  * 前端对用户可见内容进行转义；
  * 避免在 DOM 中直接插 HTML，尽量使用安全组件。
* 敏感信息：

  * 密码散列存储（Django 默认 PBKDF2）；
  * 第三方平台 token/secret 可加密存储（如用 Fernet + 环境密钥）。

## 9.2 性能 & 缓存

* 数据库：

  * 给 `tenant_id` + 常用外键建立联合索引；
  * Flow Run / NodeRun 可以按时间分区或归档，避免无限膨胀。
* 缓存：

  * Permission 缓存：key 包含 `tenant_user_id` + 资源类型，可设置 TTL=5 分钟；
  * ResourceTree 缓存：以租户为粒度缓存整棵树，TTL=10 分钟；
  * 看板查询缓存：按 dataset + widget + filter hash 做 1 分钟缓存（可选）。
* 前端：

  * 路由级代码分割；
  * 表格支持虚拟滚动，避免一次渲染太多行；
  * 搜索防抖（300–500ms）。

---

# 10. 总体注意事项（汇总版）

1. **权限统一出口**：所有业务权限统一走 PermissionService + DRF 权限类，避免在 view/middleware 到处散逻辑。
2. **多租户强制隔离**：ORM 层统一 TenantManager；Raw SQL 统一通过 sql_builder，把 `tenant_id` 和 `rowFilter` 写死在流程中。
3. **调度单点**：只用 Celery Beat 做调度，不要每个 Django 实例自行调度。
4. **LLM 只做辅助，不做单点故障**：有本地规则兜底，失败时系统仍可正常工作。
5. **JWT + 无 CSRF 的统一策略**：明确使用 Bearer Token，API 中关闭 CSRF，不要半 Cookie 半 JWT 混用。
6. **前端权限只是 UI 辅助**：后端拒绝一切无权限操作请求，前端只负责少显示按钮、减少误操作。