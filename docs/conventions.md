# 开发规范与约定 v1.0

> 适用于本多租户配置化建模 / 任务流 / 看板系统的后端（Django + DRF）与前端（Vue3 + Vben）。

---

## 0. 通用约定

1. **时间与时区**

   * 运行时与数据库统一使用 **UTC**。
   * API 返回时间字段统一使用 **ISO8601** 格式，带 `Z` 后缀，例如：`2025-01-01T00:00:00Z`。

2. **主键与 ID**

   * 所有业务主键字段统一命名为 `id`。
   * 主键类型统一采用 **UUID 字符串**（例如 Django `UUIDField`），避免多租户场景下通过自增 ID 推测数据规模或顺序。

3. **多租户**

   * 所有业务表必须包含 `tenant_id` 字段。
   * ORM 查询必须通过带租户过滤的 Manager/QuerySet，禁止直接对业务表做“无 tenant 条件”的查询。
   * 所有原生 SQL 必须通过统一构造工具（如 `sql_builder`）生成，并强制注入 `tenant_id` 过滤条件。

---

## 1. 代码规范

### 1.1 命名规范

#### 1.1.1 Python（后端）

* 模块与包名：小写 + 下划线，例如：`user_service.py`, `permission_middleware.py`。
* 类名：PascalCase，例如：`GlobalUser`, `TableService`。
* 函数与变量名：小写 + 下划线，例如：`get_user_by_id`, `tenant_id`。
* 常量名：全大写 + 下划线，例如：`MAX_PAGE_SIZE`。
* 模型字段：

  * 一律小写 + 下划线：`created_at`, `tenant_id`, `is_active`；
  * 外键字段统一 `{model}_id`：`tenant_id`, `user_id`, `table_id`；
  * 布尔字段使用 `is_` / `has_` 前缀。

#### 1.1.2 TypeScript / JavaScript（前端）

* 文件/目录：kebab-case，例如：`table-list.vue`, `flow-editor.vue`。
* 变量与函数：camelCase，例如：`getUserById`, `tenantId`。
* 类型、接口、枚举：PascalCase，例如：`UserInfo`, `PermissionLevel`。
* 组件名：PascalCase，例如：`UserList`, `FlowCanvas`。
* Composable：`use` 前缀，例如：`usePermission`, `useTenant`.

---

### 1.2 分层与组织

#### 1.2.1 后端分层

推荐分层结构：

* **View 层**

  * 处理 HTTP 请求/响应；
  * 调用 Service；
  * 做简单参数转换与基础权限判断（如是否登录）。
* **Service 层**

  * 承载业务逻辑；
  * 负责事务与跨多个 Model 的处理；
  * 对外暴露清晰方法，例如：`create_table`, `run_flow`。
* **Model 层**

  * 仅负责数据结构、字段、基础领域行为；
* **Serializer 层**

  * 负责参数校验与序列化。

**禁止跨层调用（原则）**

* Service 不调用 View；
* Model 不依赖 Service 或 View。

**务实例外原则**

* 对于**纯 CRUD、无复杂业务逻辑**的接口，允许 View 直接使用 Model + Serializer；
* 一旦该接口增加跨表逻辑、事务或复杂规则，必须引入 Service，并将对应逻辑迁移到 Service。

#### 1.2.2 前端组件组织

* **Views**：路由页面，负责页面结构与多个业务组件的组合；
* **业务组件**：带具体领域含义，可在多个页面之间复用；
* **基础组件**：通用 UI 包装，例如通用表格、通用搜索表单；
* **Layouts**：整体布局（顶栏、侧边栏等）。

原则：

* 单一职责：每个组件只做一件事；
* 业务逻辑尽量抽到 Composables（`useXXX`）中，保证组件尽量“瘦”。

---

### 1.3 注释与文档

* Python：

  * 模块、类、关键公共方法建议使用 docstring，清楚写明入参、返回值与异常。
  * 行内注释只在逻辑难以一眼看懂时使用。
* TypeScript：

  * 对外导出的函数、接口、重要组件属性建议使用 JSDoc 形式注释。

注释重点描述“为什么这么做”，不要简单复述代码本身。

---

### 1.4 代码格式

* Python：统一使用 Black + isort，行宽 100。
* TypeScript：统一使用 Prettier + ESLint，行宽 100，单引号、结尾分号。

工程中需提供统一配置文件（`pyproject.toml`, `.eslintrc`, `.prettierrc` 等）。

---

## 2. API 设计规范

### 2.1 基本风格

* 风格：RESTful。
* 版本：所有 API 统一挂载在 `/api/v1/` 下。
* 资源命名：

  * 统一使用**复数**名词、小写、连字符：`/api/v1/tables/`, `/api/v1/tenant-users/`；
* 动作类操作使用子路径：

  * 如执行任务流：`POST /api/v1/flows/{id}/run/`。

### 2.2 请求规范

* 认证 Header：

  * `Authorization: Bearer {jwt_token}`
* 追踪 Header（可选）：

  * `X-Request-ID: {uuid}`
* 租户 Header（如未从 Token 中解析）：

  * `X-Tenant-ID: {tenant_id}`
* 请求体：

  * 一律 `Content-Type: application/json`；
  * 使用 DRF Serializer 做校验。

### 2.3 统一响应结构

所有接口的响应（成功或失败）统一为：

```jsonc
{
  "code": 200,                 // 业务状态码，200 表示成功
  "message": "success",        // 提示信息
  "data": { ... },             // 具体数据；对于列表封装分页信息
  "timestamp": "2025-01-01T00:00:00Z" // 服务器时间（UTC）
}
```

* 对于分页列表：

  * `data` 内统一结构为：

    * `results`: 列表数据；
    * `count`: 总数；
    * `page`: 当前页；
    * `page_size`: 页大小；
    * `total_pages`: 总页数。

**后端约定**

* 所有成功响应必须通过一个统一的响应封装工具（如 `ok()`）生成；
* 封装工具负责：

  * 设置 `code`、`message`；
  * 填充当前 `timestamp`（UTC ISO8601）；
  * 设置 HTTP 状态码（200/201/204）。

**前端约定**

* 所有请求统一通过封装过的 axios 实例；
* axios 响应拦截器负责：

  * 校验 `code`；
  * 非 200 时统一弹出错误提示，并抛出异常；
  * 正常时直接返回 `data`（调用方只拿解包后的 `data`）。

### 2.4 状态码规范

* HTTP 状态码：

  * 2xx：请求成功（200/201/204）；
  * 4xx：客户端错误（400/401/403/404/409 等）；
  * 5xx：服务器错误（500 及以上）。
* 业务 `code`：

  * 200：成功；
  * 其他与 HTTP 状态码保持一致即可，例如 400、403、404 等。

### 2.5 版本控制

* 当前只实现 `/api/v1/**`；
* 如未来有不兼容升级，新增 `/api/v2/**`；
* 不使用 Header 版本控制方案（避免复杂度）。

---

## 3. 异常处理规范

### 3.1 异常分类（后端）

* 业务异常：

  * 校验失败（ValidationError）；
  * 权限不足（PermissionDenied）；
  * 资源不存在（ResourceNotFound）；
  * 业务冲突（例如重复编码、业务规则不满足）。
* 系统异常：

  * 数据库错误；
  * 外部服务错误（如 LLM 调用失败、Redis 连不上）；
  * 未预期错误（InternalServerError）。

### 3.2 全局异常处理器

* 使用 DRF 的 `EXCEPTION_HANDLER` 自定义异常处理器；
* 要求：

  * 将所有异常统一包装为前述 `ApiResponse` 结构；
  * `code` 使用 HTTP 状态码；
  * `message` 使用简明可读的文本（避免直接把异常栈信息返回给前端）；
  * `errors` 字段存放字段级错误详情（如有），没有则可以为空。

### 3.3 前后端配合

* 前端不得依赖 HTTP 状态码以外的特殊表现来判断成功或失败；
* 所有业务错误都通过统一弹窗或消息提示展示 `message`；
* 对于 401/403 等身份问题，可根据 `code` 做统一跳转（如跳登录页）。

---

## 4. 日志规范

### 4.1 日志级别

* DEBUG：开发调试；
* INFO：记录正常业务流程（如创建表、执行任务流）；
* WARNING：异常但不会中断主要业务流程；
* ERROR：业务失败或功能异常；
* CRITICAL：系统整体不可用或严重错误。

### 4.2 日志格式

统一格式中必须包含：

* 时间（`asctime`）；
* 日志级别（`levelname`）；
* 模块名称（`module`）；
* 租户 ID（`tenant_id`）；
* 用户 ID（`user_id`）；
* 请求 ID（`request_id`）；
* 文本消息（`message`）。

例如：

```text
[INFO] 2025-01-01 10:00:00,123 modeling.services [tenant_123] [user_456] [req_789] Table created: ...
```

### 4.3 ContextFilter 约定

为避免日志 formatter 中引用 `tenant_id` 等字段时未传导致报错，必须：

* 引入统一的日志 Filter（例如 `ContextFilter`），对每条日志记录：

  * 如未包含 `tenant_id`，填充为 `"-"`；
  * 如未包含 `user_id`，填充为 `"-"`；
  * 如未包含 `request_id`，填充为 `"-"`。
* 在所有 handler 上挂这个 Filter。

### 4.4 关键日志场景

必须记录日志的操作包括但不限于：

* 用户登录 / 登出；
* 租户创建、启用、停用；
* 表、任务流、看板的创建、更新、删除；
* 权限变更（角色、权限配置）；
* 任务流执行开始、结束、失败；
* 调用外部服务失败（如 LLM、数据库、Redis）；
* 全局异常处理器捕获的异常。

---

## 5. 数据库规范

### 5.1 表设计

* 表名：小写 + 下划线 + 复数：

  * `global_users`, `tenant_users`, `tables`, `fields`, `flows`。
* 主键字段名统一为 `id`（UUID 字符串）。
* 外键字段名统一 `{model}_id`：

  * `tenant_id`, `user_id`, `table_id`, `flow_id` 等。
* 时间字段统一：

  * `created_at`, `updated_at`，类型为 DateTime，存 UTC。
* 布尔字段统一使用 `is_` / `has_` 前缀。
* 状态字段统一为 `status`，使用预定义枚举值（如 `ACTIVE`, `DISABLED`）。

### 5.2 索引与性能

* 对主键、外键自动/显式建索引；
* 业务高频字段建索引，如：

  * `tenant_id`, `status`, `code`；
* 对组合查询场景，建立组合索引（例如 `(tenant_id, status)`）。

### 5.3 迁移

* 所有模型变更必须生成迁移文件；
* 禁止修改已经上线使用的迁移文件；
* 涉及大表的结构变更需要事先评估锁表时间、必要时采用分步迁移策略。

---

## 6. 测试规范

### 6.1 测试类型

* 单元测试（Unit Test）：

  * 针对 Service、工具函数、DSL 解析等；
  * 不依赖外部服务或尽量用 mock。
* 集成测试（Integration Test）：

  * 针对 API、任务流执行等，需要配合测试数据库。
* 端到端测试（E2E，可视情况后期补充）：

  * 从前端到后端的整体流程验证。

### 6.2 覆盖重点

**优先保证以下模块的测试覆盖：**

* 权限系统：

  * `PermissionService` 的权限合并、资源权限、列/行权限计算；
* DSL & SQL 构造：

  * 过滤表达式解析；
  * SQL 生成与注入防护；
* 任务流执行：

  * DAG 拓扑执行；
  * 重试逻辑；
  * 失败恢复与状态管理。

### 6.3 覆盖率目标

* 全局单元测试覆盖率目标：**≥ 80%**；
* 核心模块（权限、DSL、Flow Engine）尽量接近或达到 **≥ 90%**；
* 对简单 CRUD API 可适当降低要求，视开发节奏调整。

---

## 7. Git 工作流规范

### 7.1 分支策略

* `main`：生产稳定分支；
* `develop`：开发集成分支；
* `feature/*`：新功能分支；
* `bugfix/*`：普通 Bug 修复；
* `hotfix/*`：生产紧急修复。

### 7.2 提交信息规范

* 格式：`<type>(<scope>): <subject>`
* type：

  * `feat`：新功能；
  * `fix`：Bug 修复；
  * `docs`：文档；
  * `style`：代码风格；
  * `refactor`：重构；
  * `test`：测试相关；
  * `chore`：构建/工具相关。

示例：`feat(modeling): add LLM-based table code generation`

---

## 8. 文档规范

### 8.1 API 文档

* 使用 `drf-spectacular` 生成 OpenAPI 文档；
* 要求：

  * 每个接口写明用途、请求参数、响应结构示例；
  * 响应示例必须符合统一 `ApiResponse<T>` 包装结构。

### 8.2 架构与设计文档

至少包含以下内容：

* 系统总体架构图；
* 模块边界说明（平台后台 / 建模 / 任务流 / 看板 / 权限 / LLM 模块）；
* 核心数据模型 ER 图；
* DSL 设计与 SQLBuilder 说明；
* 权限模型与行列权限规则说明。

---

## 9. 安全规范

### 9.1 输入与输出

* 所有外部输入（包括前端调用、Webhook 等）必须进行参数校验；
* 字符串长度、枚举值范围、正则格式等必须在 Serializer 层校验；
* 输出内容避免包含敏感信息（密码、Token、密钥等）。

### 9.2 认证与权限

* 认证机制：JWT（Access Token + Refresh Token）。
* 所有需要登录的 API：

  * 必须检查 JWT；
  * 不仅仅依赖前端路由保护。
* 权限检查：

  * 对资源级别调用统一的 `PermissionService`；
  * 前端仅做 UI 级别控制，后端是最终权限裁决者。

### 9.3 敏感信息

* 密码使用框架默认哈希方式存储；
* 不在日志中记录：

  * 密码；
  * JWT Token；
  * 各电商平台 secret / key；
* 第三方凭证（如访问电商平台的 Access Token）需加密或安全存储。

---

## 10. 性能规范

### 10.1 数据库与查询

* 严禁在高 QPS 接口中做无分页的全表扫描；
* 所有列表接口必须分页；
* 避免 N+1 查询，合理使用 ORM 的关联预取。

### 10.2 缓存策略

* 权限结果：

  * 可基于 `tenant_user` + 资源维度做短期缓存；
* 资源树：

  * 按租户缓存树结构，TTL 建议 5 分钟；
* 看板数据：

  * 对高频访问的统计结果可做短期缓存，TTL 按业务需求设置。

### 10.3 异步任务

* 必须通过 Celery 等任务队列异步执行的场景：

  * 任务流执行（Flow Run）；
  * 大批量数据导入/导出；
* LLM 调用：

  * 目前仅用于表编码、字段编码等低频交互场景，统一设计为**同步**调用；
  * 若未来引入高频、批量生成或 embedding 计算，再考虑异步化。

### 10.4 前端性能

* 路由级代码分割；
* 需要渲染大数据量表格的页面使用虚拟滚动；
* 搜索/过滤统一加防抖（防止输入过程触发大量请求）。
