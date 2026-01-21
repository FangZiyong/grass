# AI 开发任务清单（修正版｜含“每任务改动文件”）

生成日期：2025-12-28

> 输入材料：prd.md / tech.md / architecture.md / task.md  
> 目标：在不改变原任务颗粒度与验收口径的前提下，补齐“每个任务要改哪些文件”，并修正任务拆分与文档/架构不一致之处。

## 本次发现的主要问题与修正点（已体现在任务卡中）

1. **缺少“每任务改动文件”**：已为所有任务补充 `### 涉及文件`（按 architecture.md 的目录结构给出主改动文件）。
2. **引用了不存在的文档名**：将任务中 `architecture copy.md` 统一修正为 `architecture.md`。
3. **资源树缺少 DELETE 节点任务**：补充 `T4.7`（DELETE node），并包含递归/保护规则。
4. **执行底座缺失**：tech.md 明确 reports 的 Refresh/Export 走 TaskRunInstance 执行框架，因此补充 `T0.6`（execution app）。
5. **对象存储缺失**：导出需要返回 `file_url`，补充 `T0.7`（StorageClient，LOCAL/S3 兼容）。
6. **文档内部冲突项（保守处理）**：PRD/Tech 对“通知中心”有互相矛盾的描述；原 task.md 未包含通知任务。本清单保持与原 task.md 一致：**通知中心不作为 V1 必做**，若你确认要做，可单独新增一组通知模块任务（基于 architecture.md notifications/）。

---

# AI 开发任务卡清单（V1.3｜极简章节引用版）

- 生成日期：2025-12-27
- 全局规范：全局规范统一对照：tech.md §0.3（冻结规则）、§1.5（质量红线）、§3.3（统一返回/错误码）、§3.9（请求约定/TenantContext/分页），以及 prd.md 附录A（URL/Path 参数命名）。

## 任务索引
- **T0.1**：项目启动骨架：settings/urls/asgi/wsgi + /healthz（统一壳）
- **T0.2**：统一错误码与全局异常处理：common/errors + DRF exception handler
- **T0.3**：请求链路基础设施：Request-ID 中间件 + 结构化日志
- **T0.4**：认证上下文：AccessToken 解析 + request.user 注入（AuthContext）
- **T0.5**：TenantContext 中间件：tenant_id 解析/校验 + 租户停用拦截
- **T1.1**：accounts 域模型与迁移：GlobalUser/AuthSession（含索引/唯一约束）
- **T1.2**：登录接口：POST /api/auth/login（含 session 落库 + 单测）
- **T1.3**：刷新接口：POST /api/auth/refresh（refresh cookie → 新 access_token）
- **T1.4**：登出接口：POST /api/auth/logout（撤销 refresh session）
- **T1.5**：我的信息：GET /api/me（返回用户 + 当前租户上下文）
- **T2.1**：tenants 域模型与迁移：Tenant/TenantUser（含状态/owner 标识）
- **T2.2**：租户列表：GET /api/tenants（当前用户可访问的租户）
- **T2.3**：租户切换：POST /api/tenants/switch（更新最近租户）
- **T3.1**：iam 域模型与迁移：Role/RolePermission/RowPermission/ColumnPermission/Grant 等
- **T3.2**：角色管理：/api/tenants/{tenant_id}/roles（GET/POST/PATCH/DELETE）
- **T3.3**：成员绑定角色：POST/DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/roles
- **T3.4**：Owner 设定：POST/DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/owner
- **T3.5**：角色资源授权：GET/PUT /api/tenants/{tenant_id}/roles/{role_id}/resource-permissions
- **T3.6**：权限面板数据：GET /api/permissions/resources/{resource_node_id}
- **T3.7**：创建/更新授权：POST /api/permissions/grants + 撤销授权 DELETE /api/permissions/grants/{grant_id}
- **T3.8**：列级权限：GET/PUT /api/tenants/{tenant_id}/tables/{table_id}/column-permissions
- **T3.9**：行级权限：/api/tenants/{tenant_id}/tables/{table_id}/row-permissions（GET/POST/PATCH/DELETE）
- **T4.1**：resource_tree 域模型与迁移：ResourceNode + 根节点初始化（按 scope）
- **T4.2**：资源树子节点查询：GET /api/resource-trees/{scope}/children
- **T4.3**：创建文件夹：POST /api/resource-trees/{scope}/folders
- **T4.4**：重命名节点：PATCH /api/resource-trees/{scope}/nodes/{node_id}
- **T4.5**：移动节点：POST /api/resource-trees/{scope}/move
- **T4.6**：同级排序：POST /api/resource-trees/{scope}/reorder
- **T5.1**：数据仓库集成基建：DW 连接管理 + SQL 执行器（按租户隔离）
- **T5.2**：DW DDL：建表/删表/改表（供 modeling 使用）
- **T6.1**：modeling 域模型与迁移：ModelingTable/ModelingField/（可选 Records）
- **T6.2**：建模表接口：/api/modeling/tables（GET/POST/GET detail/PATCH/DELETE）+ 资源树挂载
- **T6.3**：建模字段接口：/api/modeling/tables/{table_id}/fields（GET/POST/PATCH/DELETE）+ reorder
- **T6.4**：引用候选：GET /api/modeling/tables/{ref_table_id}/reference-candidates
- **T6.5**：数据查询：POST /api/modeling/tables/{table_id}/data/query（走 QueryEngine）
- **T6.6**：记录 CRUD：/api/modeling/tables/{table_id}/records（创建/更新/删除/批量删可选）
- **T7.1**：统一 FilterDSL：schema + validator + compiler（AST→SQL）
- **T7.2**：QueryBuilder：将 Dataset/Chart 的 QuerySpec 编译为 SQL（含行列权限叠加）
- **T7.3**：查询校验：POST /api/query/validate（校验并预编译）
- **T7.4**：执行查询：POST /api/query/run（执行并返回结果集）
- **T7.5**：导出 CSV：POST /api/query/export/csv（异步 ExportJob）
- **T8.1**：reports 域模型与迁移：Dataset/Chart/Dashboard/DashboardItem/ExportJob/RefreshRun
- **T8.2**：Datasets CRUD：/api/datasets（GET/POST/GET detail/PATCH）+ 资源树挂载
- **T8.3**：Dataset 启用/禁用：POST /api/datasets/{dataset_id}/enable（以及 disable 若 tech 有）
- **T8.4**：Dataset Refresh：POST /api/datasets/{dataset_id}/refresh + GET refresh-runs
- **T8.5**：Dataset Preview：POST /api/datasets/{dataset_id}/preview（走 QueryEngine）
- **T8.6**：Charts：POST /api/charts/preview + Charts CRUD（/api/charts）
- **T8.7**：Chart 导出：POST /api/charts/{chart_id}/exports + GET /api/exports/{export_job_id}
- **T8.8**：Dashboards CRUD：/api/dashboards（GET/POST/GET detail/PATCH）
- **T8.9**：Dashboard Items & Layout：items 增删改 + PUT layout
- **T9.1**：flows/execution 域模型与迁移：Flow/FlowGraph/Schedule/FlowRun/NodeRun/Logs
- **T9.2**：Flow CRUD：/api/flows（GET/POST/GET detail/PATCH/DELETE）+ 资源树挂载
- **T9.3**：Flow Graph：GET/PUT /api/flows/{flow_id}/graph（保存 DAG）
- **T9.4**：Flow Validate：POST /api/flows/{flow_id}/validate（校验可运行）
- **T9.5**：Flow Schedule：GET/PUT /api/flows/{flow_id}/schedule（cron/启停）
- **T9.6**：触发运行与运行列表：POST/GET /api/flows/{flow_id}/runs（防重复运行）
- **T9.7**：运行态查询：GET /api/flow-runs/{run_id} + node-runs + node-run detail + logs
- **T9.8**：执行框架：ExecutionRegistry + Celery Worker 执行节点（状态机与重试）
- **T10.1**：audit_logs 域模型与迁移：AuditLog（含 tenant_id + platform 范围）
- **T10.2**：审计写入器：AuditWriter（内部服务）+ 在关键写操作挂钩
- **T10.3**：租户审计 API：GET /api/audit-logs + detail + meta/actions + meta/target-types
- **T10.4**：平台审计 API：GET /api/platform/audit-logs (+ meta) + detail
- **T11.1**：平台后台鉴权与路由分组：/admin/api/*（强制 platform_admin 权限）
- **T11.2**：平台用户列表：GET /admin/api/users（GlobalUser 列表）
- **T11.3**：平台用户管理：GET/PATCH /admin/api/users/{user_id} + enable/disable + reset_password
- **T11.4**：创建租户：POST /admin/api/tenants（创建 tenant + 初始化资源树 root）
- **T11.5**：编辑租户：PATCH /admin/api/tenants/{tenant_id}（必须支持改名称）
- **T11.6**：租户启停：POST /admin/api/tenants/{tenant_id}/enable & /suspend
- **T11.7**：添加租户成员：POST /admin/api/tenants/{tenant_id}/users（支持批量）
- **T11.8**：租户成员编辑：PATCH /admin/api/tenants/{tenant_id}/users/{tenant_user_id}（及查询）
- **T12.1**：LLM Assist：POST /api/assist/code-suggest（编码/命名建议）
- **T13.1**：API 路由一致性与 Schema 输出：确保 endpoints 与 tech/prd 命名规范一致
- **T13.2**：端到端冒烟测试：登录→切租户→建模建表→建 dataset→chart preview→创建 flow→触发 run
- **T13.3**：质量门禁：lint/format/typecheck/coverage（CI）

## 任务卡正文

## T0.1 项目启动骨架：settings/urls/asgi/wsgi + /healthz（统一壳）

### 对照章节
- architecture.md §0. 目标与约束


### 涉及文件
- `src/config/settings/base.py`
- `src/config/settings/dev.py`
- `src/config/urls.py`
- `src/api/v1/urls.py`
- `src/api/v1/schema.py`
- `pyproject.toml / requirements.txt（如需补依赖）`

### 目标
服务可启动，并通过 GET /healthz 返回统一壳 OK

### 范围
**包含**
- 补齐 Django/DRF 基础配置（settings/urls/asgi/wsgi）
- 挂载 /api 路由前缀与 /healthz
- 最小化依赖：本任务不引入业务 app

**不包含**
- 不实现任何业务接口（auth/tenants/modeling/...）

### 接口契约
- URL：GET /healthz
- 权限：公开
- 出参（统一壳 data）：{status:"ok"}

### 验收标准（DoD）
- ✅ 单测覆盖：至少 2 个分支（正常；404/500 处理可选）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T0.2 统一错误码与全局异常处理：common/errors + DRF exception handler

### 对照章节
- （本任务除全局规范外无额外章节依赖）


### 涉及文件
- `src/common/http/response.py`
- `src/common/http/pagination.py`
- `src/common/errors/codes.py`
- `src/common/errors/exceptions.py`
- `src/common/errors/handlers.py`
- `src/config/settings/base.py（DRF/ExceptionHandler 配置）`

### 目标
业务异常、校验异常、权限异常均返回统一壳与规范错误码

### 范围
**包含**
- 实现错误码枚举（codes.py）与业务异常（exceptions.py）
- 实现 DRF exception handler（handlers.py）并在 settings 注册
- 覆盖常见异常：ValidationError / NotAuthenticated / PermissionDenied / Http404 / IntegrityError

**不包含**
- 不在此任务里实现每个业务模块的全量错误码（按 tech 已出现的先落地）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个关键分支（400/401/403/404/409/500）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T0.3 请求链路基础设施：Request-ID 中间件 + 结构化日志

### 对照章节
- architecture.md §0. 目标与约束（可观测性）


### 涉及文件
- `src/common/middleware/request_id.py`
- `src/config/logging.py`
- `src/config/settings/base.py（middleware / logging 配置）`

### 目标
每个请求都有 request_id，并在日志与响应壳中可追踪

### 范围
**包含**
- 实现 request_id middleware（注入 request.state/request.META）
- 日志格式带 request_id、tenant_id（若已解析）、user_id（若已鉴权）

**不包含**
- 不接入外部 APM（Sentry/OTel）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 3 个分支（无 header；有 header；异常路径）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T0.4 认证上下文：AccessToken 解析 + request.user 注入（AuthContext）

### 对照章节
- tech.md §4.3 认证与会话（Auth）
- tech.md §4.7 接口实现规范（逐接口：入参/出参/校验/错误码/伪代码）
- architecture.md accounts ｜账号与认证 > Services/API


### 涉及文件
- `src/common/middleware/auth_context.py`
- `src/apps/accounts/services/tokens.py`
- `src/apps/accounts/api/permissions.py`
- `src/config/settings/base.py（AUTH/JWT 相关配置）`

### 目标
携带有效 access token 的请求可获得 request.user，并能被权限系统使用

### 范围
**包含**
- 实现 access token 的签发/验签工具（JWT 或 tech 指定方案）
- 实现 AuthContext middleware 或 DRF authentication class
- 为后续权限判断提供 user_id、is_platform_admin 等字段

**不包含**
- 不实现 refresh cookie 与 session 落库（放到 accounts 模块任务）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（无 token；token 过期；签名错；正常；禁用用户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T0.5 TenantContext 中间件：tenant_id 解析/校验 + 租户停用拦截

### 对照章节
- tech.md §4.5.3 登录后租户跳转（单租户 / 多租户 / 最近租户）
- prd.md §2 系统角色与访问边界
- architecture.md tenants ｜租户切换


### 涉及文件
- `src/common/middleware/tenant_context.py`
- `src/apps/tenants/services.py`
- `src/apps/tenants/selectors.py`
- `src/apps/accounts/models/sessions.py（最近租户/会话字段落库）`
- `src/apps/tenants/api/views_tenants.py`
- `src/config/settings/base.py（middleware 顺序）`

### 目标
所有租户侧请求可稳定解析 tenant_id，并对 SUSPENDED tenant 拒绝访问

### 范围
**包含**
- 实现 tenant_context middleware（解析 header/cookie/last_tenant）
- 校验用户是否属于 tenant（TenantUser）
- SUSPENDED tenant 返回 403（统一壳/错误码）

**不包含**
- 不实现租户创建（平台后台任务）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（header/last_tenant；无成员；suspended；正常；未登录；错误 tenant_id）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）


## T0.6 执行底座基建：TaskRunInstance + SchedulerTick + WorkerBase（execution app）

### 对照章节
- tech.md §9.1（DatasetRefresh 与 Export 统一走 TaskRunInstance 执行框架）
- architecture.md execution 模块目录结构与模型定义

### 涉及文件
- `src/apps/execution/models/task_run.py`
- `src/apps/execution/models/task_log.py（可选）`
- `src/apps/execution/registry/tasks.py`
- `src/apps/execution/scheduler/dispatcher.py`
- `src/apps/execution/worker/base.py`
- `src/apps/execution/management/commands/scheduler_tick.py`
- `src/config/celery.py`
- `src/config/settings/base.py（INSTALLED_APPS / CELERY 配置）`
- `src/tests/test_execution_smoke.py（新增）`

### 目标
实现可复用的“任务执行底座”，让 reports/flows 的异步任务统一：可追踪、可重试、可审计、可幂等。

### 范围
**包含**
- TaskRunInstance（task_run_instance）基础字段、状态机、索引
- TaskRunLog（可选）用于记录 worker 侧关键日志片段（避免跑满 audit_logs）
- task_type -> handler 注册表（ExecutionRegistry）
- scheduler_tick：扫描 READY/RUNNING 的任务并派发（可用 Celery delay 或直接调用）
- worker base：统一处理重试、超时、异常映射、写回状态

**不包含**
- UI/前端展示
- 复杂优先级/队列治理（后续版本）

### 接口契约
（本任务不直接暴露对外 HTTP 接口；由 reports/flows 通过内部 service 调用）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（状态迁移、重试、handler 异常、超时、幂等、并发抢占）
- ✅ migrations 可运行（新建执行表）
- ✅ 与统一错误码/返回壳兼容（tech.md §3.3）
- ✅ scheduler_tick 可在本地跑通：创建一条 TaskRunInstance → tick → worker 执行 → 状态完成


## T0.7 文件存储集成基建：StorageClient（本地文件系统/S3 兼容）+ file_url 生成

### 对照章节
- tech.md §9.1（导出文件上传到对象存储并返回 file_url）
- architecture.md integrations/storage 目录设计

### 涉及文件
- `src/integrations/storage/client.py（新增）`
- `src/integrations/storage/__init__.py（新增）`
- `src/integrations/__init__.py（可能补导出）`
- `src/config/settings/base.py（存储配置：LOCAL/S3 等）`
- `src/tests/test_storage_client.py（新增）`

### 目标
提供统一的文件上传/下载 URL 生成能力，供 ExportJob（CSV/PNG）复用。

### 范围
**包含**
- StorageClient：put_bytes / put_file / get_presigned_url（若 S3）
- LOCAL 模式：落本地目录（用于测试/开发）
- S3 模式：预留接口（可先 mock，不强依赖真实 S3）
- 错误映射到统一错误码

**不包含**
- 大文件分片/断点续传
- 权限签名细粒度策略（后续版本）

### 接口契约
（内部服务，不直接对外暴露 HTTP）

### 验收标准（DoD）
- ✅ 单测覆盖：LOCAL put/get、路径穿越防护、非法 content-type、异常映射
- ✅ 可被 ExportJob 调用并返回稳定 file_url（本地模式）


## T1.1 accounts 域模型与迁移：GlobalUser/AuthSession（含索引/唯一约束）

### 对照章节
- tech.md §4.2 数据表（User/Tenant/AuthSession）
- tech.md §4.2.4 auth_session（登录会话 / RefreshToken 存储）
- architecture.md accounts ｜账号与认证 > 模型（与 tech.md 数据表对齐）


### 涉及文件
- `src/apps/accounts/models/users.py`
- `src/apps/accounts/models/sessions.py`
- `src/apps/accounts/migrations/*`

### 目标
完成 accounts 相关表结构与迁移，migrate 后可创建用户与会话记录

### 范围
**包含**
- GlobalUser（邮箱/状态/密码哈希/last_login_at/is_platform_admin 等）
- AuthSession（refresh token、过期时间、撤销、user_id、device_info 可选）
- 必要索引与唯一约束（email/login_name）

**不包含**
- 不实现业务接口

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 3 个分支（创建用户；重复邮箱冲突；创建 session）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T1.2 登录接口：POST /api/auth/login（含 session 落库 + 单测）

### 对照章节
- tech.md §4.7.1 `POST /api/auth/login`
- tech.md §4.3 认证与会话（Auth）
- prd.md §6 租户通用体验（Tenant Workspace Shell）（登录与进入工作区）


### 涉及文件
- `src/apps/accounts/api/views_auth.py`
- `src/apps/accounts/api/serializers.py`
- `src/apps/accounts/services/auth.py`
- `src/apps/accounts/services/tokens.py`
- `src/apps/accounts/tests/test_auth.py`
- `src/apps/accounts/api/urls.py`

### 目标
输入 login_name+password 成功返回 access_token 并下发 HttpOnly refresh cookie

### 范围
**包含**
- serializer 校验（必填/格式）
- 校验凭证并签发 token
- 创建 AuthSession（refresh token 落库）
- 按 tech 规则处理单租户/多租户/最近租户跳转所需字段（如 last_tenant_id）

**不包含**
- 不实现注册/找回密码（若 PRD 明确 out-of-scope）

### 接口契约
- URL：POST /api/auth/login
- 权限：公开
- 入参：{login_name, password}
- 出参 data：{access_token, expires_in, user:{...}, tenant:{...}?}
- 错误码：AUTH_INVALID_CREDENTIALS(401)、AUTH_USER_DISABLED(403)、AUTH_TOO_MANY_ATTEMPTS(429)、VALIDATION_*(400)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 7 个关键分支（成功/密码错/用户禁用/参数缺失/刷新 cookie/最近租户/限流-可 mock）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T1.3 刷新接口：POST /api/auth/refresh（refresh cookie → 新 access_token）

### 对照章节
- tech.md §4.6.1 全局认证与用户态
- tech.md §4.2.4 auth_session（refresh 存储与撤销）
- architecture.md accounts ｜账号与认证 > API


### 涉及文件
- `src/apps/accounts/api/views_auth.py`
- `src/apps/accounts/api/serializers.py`
- `src/apps/accounts/services/tokens.py`
- `src/apps/accounts/models/sessions.py`
- `src/apps/accounts/tests/test_auth.py`

### 目标
携带有效 refresh cookie 可换取新 access_token，并按策略轮换 refresh

### 范围
**包含**
- 读取 refresh cookie → 查 AuthSession
- 校验未撤销/未过期/与 user 匹配
- 签发新 access_token（可选：refresh rotation）

**不包含**
- 不实现第三方登录

### 接口契约
- URL：POST /api/auth/refresh
- 权限：公开（但需有效 refresh cookie）
- 入参：无
- 出参 data：{access_token, expires_in}
- 错误码：AUTH_SESSION_EXPIRED(401)、AUTH_SESSION_REVOKED(401)、AUTH_INVALID_TOKEN(401)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（成功/过期/撤销/签名错/无 cookie/用户禁用）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T1.4 登出接口：POST /api/auth/logout（撤销 refresh session）

### 对照章节
- tech.md §4.6.1 全局认证与用户态
- architecture.md accounts ｜账号与认证 > API


### 涉及文件
- `src/apps/accounts/api/views_auth.py`
- `src/apps/accounts/services/auth.py`
- `src/apps/accounts/models/sessions.py`
- `src/apps/accounts/tests/test_auth.py`

### 目标
调用 logout 后 refresh session 被撤销，后续 refresh 失败

### 范围
**包含**
- 撤销当前 refresh 对应的 AuthSession
- 清理 refresh cookie（Set-Cookie 过期）

**不包含**
- 不做全端登出（撤销所有 session）

### 接口契约
- URL：POST /api/auth/logout
- 权限：已登录（建议）
- 出参：统一壳 OK
- 错误码：AUTH_INVALID_TOKEN(401)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（正常；无 session；已撤销；未登录）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T1.5 我的信息：GET /api/me（返回用户 + 当前租户上下文）

### 对照章节
- tech.md §4.7.2 `GET /api/me`
- architecture.md accounts ｜账号与认证 > API


### 涉及文件
- `src/apps/accounts/api/views_me.py`
- `src/apps/accounts/api/serializers.py`
- `src/apps/accounts/selectors.py`
- `src/apps/accounts/tests/test_me.py`

### 目标
登录后调用 /api/me 返回 user 信息与 tenant 上下文（若已解析）

### 范围
**包含**
- 返回 user 基本信息（字段命名以 `*_id` 形式）
- 若有 TenantContext，附带 tenant（上下文字段按 tech，使用 `tenant_id`）

**不包含**
- 不返回敏感字段（密码哈希/refresh token 等）

### 接口契约
- URL：GET /api/me
- 权限：已登录
- 出参 data：{user:{user_id,...}, tenant?:{tenant_id,code,name,plan}}
- 错误码：UNAUTHENTICATED(401)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（无 tenant；有 tenant；未登录；禁用用户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T2.1 tenants 域模型与迁移：Tenant/TenantUser（含状态/owner 标识）

### 对照章节
- tech.md §4.2 数据表（Tenant/TenantUser）
- prd.md §2 系统角色与访问边界
- architecture.md tenants ｜租户切换 > 模型（与 tech.md 数据表对齐）


### 涉及文件
- `src/apps/tenants/models/tenant.py`
- `src/apps/tenants/models/tenant_user.py`
- `src/apps/tenants/migrations/*`

### 目标
完成 tenants 表结构并可创建 tenant 与成员关系

### 范围
**包含**
- Tenant（name/status 等）
- TenantUser（tenant_id/user_id/role flags: is_owner 等）
- 必要索引与唯一约束（tenant_id+user_id）

**不包含**
- 不实现平台创建租户 API（由 Platform Admin 模块）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 3 个分支（创建 tenant；加入成员；唯一约束）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T2.2 租户列表：GET /api/tenants（当前用户可访问的租户）

### 对照章节
- tech.md §4.7.3 `POST /api/tenants/switch`
- prd.md §6 租户通用体验（Tenant Workspace Shell）
- architecture.md tenants ｜租户切换 > API


### 涉及文件
- `src/apps/tenants/api/views_tenants.py`
- `src/apps/tenants/api/serializers.py`
- `src/apps/tenants/selectors.py`
- `src/apps/tenants/tests/*`

### 目标
返回当前用户可访问租户列表（含最近租户标识）

### 范围
**包含**
- 按 user_id 查询 TenantUser → Tenant
- 返回 tenant 状态并过滤不可用（按 tech/PRD）

**不包含**
- 不实现搜索/排序高级功能（若文档未要求）

### 接口契约
- URL：GET /api/tenants
- 权限：已登录
- 出参：tenant 列表
- 错误码：UNAUTHENTICATED(401)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（正常；无租户；含 suspended；未登录）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T2.3 租户切换：POST /api/tenants/switch（更新最近租户）

### 对照章节
- tech.md §4.7.3 `POST /api/tenants/switch`
- prd.md §6 租户通用体验（租户切换）
- architecture.md tenants ｜租户切换 > API


### 涉及文件
- `src/apps/tenants/api/views_tenants.py`
- `src/apps/tenants/api/serializers.py`
- `src/apps/tenants/services.py`
- `src/apps/accounts/models/sessions.py`
- `src/apps/tenants/tests/*`
- `src/common/middleware/tenant_context.py（必要时补充）`

### 目标
切换到指定 tenant，并更新用户最近租户字段

### 范围
**包含**
- 校验成员关系
- 写入 last_tenant_id（或等价实现）

**不包含**
- 不实现多租户并行上下文

### 接口契约
- URL：POST /api/tenants/switch
- 权限：已登录
- 入参：{tenant_id}
- 出参：{tenant_id}
- 错误码：TENANT_NOT_FOUND(404)、TENANT_ACCESS_DENIED(403)、TENANT_SUSPENDED(403)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（成功/不存在/无权限/suspended/参数缺失）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.1 iam 域模型与迁移：Role/RolePermission/RowPermission/ColumnPermission/Grant 等

### 对照章节
- tech.md §5.11 接口清单与实现细则（租户侧 Settings：角色/授权/行列权限）
- prd.md §4 统一查询 DSL & 权限模型（横切关注）
- architecture.md iam ｜租户内角色与权限 > 模型


### 涉及文件
- `src/apps/iam/models/roles.py`
- `src/apps/iam/models/membership.py`
- `src/apps/iam/models/grants.py`
- `src/apps/iam/models/row_perms.py`
- `src/apps/iam/models/column_perms.py`
- `src/apps/iam/migrations/*`

### 目标
完成 IAM 相关表结构与迁移，支撑后续权限/授权接口

### 范围
**包含**
- Role（租户内角色）
- TenantUserRole（成员-角色关系）
- RoleResourcePermission（角色对资源树节点的权限）
- RowPermission、ColumnPermission（按 PRD 合并规则设计）
- Grant（权限面板授权记录，若 tech/PRD 定义）

**不包含**
- 不在此任务实现权限计算（放到后续任务）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（创建角色；绑定角色；写行权限；唯一约束）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.2 角色管理：/api/tenants/{tenant_id}/roles（GET/POST/PATCH/DELETE）

### 对照章节
- tech.md §5.11.3 角色管理
- tech.md §5.11.3.1 GET /api/tenants/{tenant_id}/roles（角色列表）
- prd.md §7 租户设置模块（角色管理）


### 涉及文件
- `src/apps/iam/api/views_roles.py`
- `src/apps/iam/api/serializers_roles.py`
- `src/apps/iam/services.py`
- `src/apps/iam/selectors.py`
- `src/apps/iam/api/urls.py`
- `src/apps/iam/tests/*`

### 目标
可增删改查角色（租户内唯一），并写审计

### 范围
**包含**
- list/create/update/delete
- 输入校验（name 唯一）
- 审计：ROLE_CREATE/UPDATE/DELETE

**不包含**
- 不实现导入导出

### 接口契约
- URL：GET/POST /api/tenants/{tenant_id}/roles；PATCH/DELETE /api/tenants/{tenant_id}/roles/{role_id}
- 权限：Tenant Owner 或 ROLE_MANAGE（按 tech/PRD）
- 分页：GET list 走统一分页（tech.md §3.9）
- 错误码：ROLE_NOT_FOUND(404)、ROLE_NAME_CONFLICT(409)、PERMISSION_DENIED(403)、VALIDATION_*(400)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（CRUD + 无权限 + 冲突 + not found）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.3 成员绑定角色：POST/DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/roles

### 对照章节
- tech.md §5.11.4 成员-角色绑定
- tech.md §5.11.4.1 POST /api/tenants/{tenant_id}/users/{tenant_user_id}/roles（绑定角色）
- prd.md §7 租户设置模块（成员与角色）


### 涉及文件
- `src/apps/iam/api/views_membership.py`
- `src/apps/iam/api/serializers_membership.py`
- `src/apps/iam/services.py`
- `src/apps/iam/tests/*`

### 目标
可为 tenant_user 绑定/解绑角色，并更新有效权限缓存（如有）

### 范围
**包含**
- 绑定角色（POST）
- 解绑角色（DELETE）
- 审计：USER_BIND_ROLE/UNBIND_ROLE

**不包含**
- 不做批量绑定（若未要求）

### 接口契约
- URL：POST /api/tenants/{tenant_id}/users/{tenant_user_id}/roles；DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/roles/{role_id}
- 权限：Owner 或 USER_ROLE_MANAGE
- 错误码：TENANT_USER_NOT_FOUND、ROLE_NOT_FOUND、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（绑定/解绑/无权限/不存在/跨租户/重复绑定）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.4 Owner 设定：POST/DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/owner

### 对照章节
- tech.md §5.11.5 Owner 管理
- tech.md §5.11.5.1 POST /api/tenants/{tenant_id}/users/{tenant_user_id}/owner（设为 Owner）
- prd.md §2 系统角色与访问边界（Owner 定义）


### 涉及文件
- `src/apps/iam/api/views_membership.py`
- `src/apps/iam/api/serializers_membership.py`
- `src/apps/iam/services.py`
- `src/apps/iam/tests/*`

### 目标
可设/取消 Owner，并保证至少一个 Owner（按 PRD）

### 范围
**包含**
- 设为 Owner（POST）
- 取消 Owner（DELETE）
- 审计：OWNER_SET/OWNER_UNSET

**不包含**
- 不支持跨租户操作

### 接口契约
- URL：POST/DELETE /api/tenants/{tenant_id}/users/{tenant_user_id}/owner
- 权限：仅 Owner
- 错误码：PERMISSION_DENIED、TENANT_USER_NOT_FOUND、OWNER_MIN_ONE_VIOLATION(409)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（设/取消/无权限/不存在/最少1个/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.5 角色资源授权：GET/PUT /api/tenants/{tenant_id}/roles/{role_id}/resource-permissions

### 对照章节
- tech.md §5.11.6 资源授权（基于资源树节点）
- tech.md §5.11.6.1 GET /api/tenants/{tenant_id}/roles/{role_id}/resource-permissions（查询角色资源授权）
- prd.md §4.4 资源级权限模型（RolePermission）


### 涉及文件
- `src/apps/iam/api/views_permissions.py`
- `src/apps/iam/api/serializers_permissions.py`
- `src/apps/iam/services.py`
- `src/apps/iam/selectors.py`
- `src/apps/iam/tests/*`

### 目标
可查询/保存角色对资源树节点的权限授权

### 范围
**包含**
- GET 查询角色授权
- PUT 保存整包授权（覆盖式/增量式按 tech）
- 审计：ROLE_GRANT_SAVE

**不包含**
- 不做复杂差异合并（若 tech 明确覆盖式则覆盖式）

### 接口契约
- URL：GET/PUT /api/tenants/{tenant_id}/roles/{role_id}/resource-permissions
- 权限：Owner 或 ROLE_GRANT_MANAGE
- 入参（PUT）：[{resource_node_id, permission}]（按 tech 定义）
- 错误码：ROLE_NOT_FOUND、RESOURCE_NODE_NOT_FOUND、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 7 个分支（GET/PUT/无权限/role不存在/node不存在/非法permission/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.6 权限面板数据：GET /api/permissions/resources/{resource_node_id}

### 对照章节
- tech.md §5.11.6.3 权限面板数据
- tech.md §5.11.6.3 GET /api/permissions/resources/{resource_node_id}（权限面板数据）
- prd.md §4.4.4 多角色合并（Effective Resource Permission）


### 涉及文件
- `src/apps/iam/api/views_permissions.py`
- `src/apps/iam/api/serializers_permissions.py`
- `src/apps/iam/selectors.py`
- `src/apps/iam/tests/*`

### 目标
返回资源节点权限面板所需的角色/授权汇总信息

### 范围
**包含**
- 聚合 roles、已有 grants、effective permission 展示所需字段

**不包含**
- 不实现前端 UI 逻辑，只提供数据

### 接口契约
- URL：GET /api/permissions/resources/{resource_node_id}
- 权限：Owner 或 GRANT_VIEW
- 错误码：RESOURCE_NODE_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（正常/无权限/node不存在/跨租户/空授权）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.7 创建/更新授权：POST /api/permissions/grants + 撤销授权 DELETE /api/permissions/grants/{grant_id}

### 对照章节
- tech.md §5.11.6.4/5 授权创建更新与撤销
- tech.md §5.11.6.4 POST /api/permissions/grants（创建/更新授权）
- prd.md §4.4 资源级权限模型（RolePermission）


### 涉及文件
- `src/apps/iam/api/views_permissions.py`
- `src/apps/iam/services.py`
- `src/apps/iam/tests/*`

### 目标
可创建/更新一条授权记录，并可撤销授权

### 范围
**包含**
- POST upsert grant
- DELETE revoke grant
- 审计：GRANT_UPSERT/GRANT_REVOKE

**不包含**
- 不实现批量授权（若未要求）

### 接口契约
- URL：POST /api/permissions/grants；DELETE /api/permissions/grants/{grant_id}
- 权限：Owner 或 GRANT_MANAGE
- 错误码：VALIDATION_*、ROLE_NOT_FOUND、RESOURCE_NODE_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（create/update/delete/无权限/跨租户/非法permission/not found/幂等）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.8 列级权限：GET/PUT /api/tenants/{tenant_id}/tables/{table_id}/column-permissions

### 对照章节
- tech.md §5.11.7 列级权限
- tech.md §5.11.7.1 GET /api/tenants/{tenant_id}/tables/{table_id}/column-permissions（字段权限查询）
- prd.md §4.3 列级权限模型（ColumnPermission）


### 涉及文件
- `src/apps/iam/api/views_column_perms.py`
- `src/apps/iam/api/serializers_column_perms.py`
- `src/apps/iam/services.py`
- `src/apps/iam/tests/*`

### 目标
可查询/保存表的列级权限规则（按角色）

### 范围
**包含**
- GET 当前 table 的列权限
- PUT 保存列权限
- 审计：COLUMN_PERMISSION_SAVE

**不包含**
- 不实现列权限对查询的实际应用（在 QueryEngine 集成任务中实现）

### 接口契约
- URL：GET/PUT /api/tenants/{tenant_id}/tables/{table_id}/column-permissions
- 权限：Owner 或 TABLE_PERMISSION_MANAGE
- 错误码：TABLE_NOT_FOUND、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 7 个分支（GET/PUT/无权限/table不存在/字段不存在/非法级别/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T3.9 行级权限：/api/tenants/{tenant_id}/tables/{table_id}/row-permissions（GET/POST/PATCH/DELETE）

### 对照章节
- tech.md §5.11.8 行级权限
- tech.md §5.11.8.2 GET /api/tenants/{tenant_id}/tables/{table_id}/row-permissions（行权限查询）
- prd.md §4.2 行级权限模型（RowPermission）


### 涉及文件
- `src/apps/iam/api/views_row_perms.py`
- `src/apps/iam/api/serializers_row_perms.py`
- `src/apps/iam/services.py`
- `src/apps/iam/tests/*`

### 目标
可管理 row permission 规则（含合并规则所需字段）

### 范围
**包含**
- 列表/创建/更新/删除
- 审计：ROW_PERMISSION_*

**不包含**
- 不在此任务把 row perm 应用到查询（在 QueryEngine 集成任务中实现）

### 接口契约
- URL：GET/POST /api/tenants/{tenant_id}/tables/{table_id}/row-permissions；PATCH/DELETE /api/tenants/{tenant_id}/tables/{table_id}/row-permissions/{row_perm_id}
- 权限：Owner 或 TABLE_PERMISSION_MANAGE
- 错误码：TABLE_NOT_FOUND、ROW_PERMISSION_NOT_FOUND、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（CRUD + 校验失败 + 无权限 + 不存在 + 跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.1 resource_tree 域模型与迁移：ResourceNode + 根节点初始化（按 scope）

### 对照章节
- tech.md §6.2 资源树（Resource Tree）
- prd.md §3 核心概念与全局规范（资源树）
- architecture.md resource_tree ｜资源树 > 模型


### 涉及文件
- `src/apps/resource_tree/models/resource_node.py`
- `src/apps/resource_tree/migrations/*`

### 目标
创建 ResourceNode 表并可为每个 tenant 初始化各 scope 根节点

### 范围
**包含**
- ResourceNode（node_id/tenant_id/scope/type/name/parent_node_id/order/path 等）
- 初始化 ROOT 节点（按 tech/PRD）

**不包含**
- 不实现权限授权（由 IAM 相关任务）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（创建 root；重复 root；创建 folder；层级）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.2 资源树子节点查询：GET /api/resource-trees/{scope}/children

### 对照章节
- tech.md §6.2.5.1 GET /api/resource-trees/{scope}/children（查询子节点）
- architecture.md resource_tree ｜资源树 > API


### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/api/serializers.py`
- `src/apps/resource_tree/selectors.py`
- `src/apps/resource_tree/tests/*`

### 目标
返回指定节点的子节点列表（含 folders + resources），支持排序与分页（如 tech 要求）

### 范围
**包含**
- 按 parent_node_id 查询 children
- 按 order 返回
- 必要时支持分页/搜索（按 tech）

**不包含**
- 不返回跨 tenant 数据

### 接口契约
- URL：GET /api/resource-trees/{scope}/children?parent_node_id=...
- 权限：已登录 + scope 对应最小查看权限（由权限系统约束）
- 错误码：RESOURCE_NODE_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（root；folder；无权限；node不存在；非法scope；跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.3 创建文件夹：POST /api/resource-trees/{scope}/folders

### 对照章节
- tech.md §6.2.5.2 POST /api/resource-trees/{scope}/folders（创建文件夹）
- prd.md §3 核心概念与全局规范（资源树/Folder）


### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/api/serializers.py`
- `src/apps/resource_tree/services.py`
- `src/apps/resource_tree/tests/*`

### 目标
在指定 parent_node_id 下创建 folder 节点，并返回新节点

### 范围
**包含**
- 校验 parent 属于同 tenant+scope
- 创建节点并分配 order
- 审计：FOLDER_CREATE

**不包含**
- 不实现批量创建

### 接口契约
- URL：POST /api/resource-trees/{scope}/folders
- 入参：{parent_node_id,name}
- 权限：RESOURCE_MANAGE（由 scope 决定）
- 错误码：RESOURCE_NODE_NOT_FOUND、NAME_CONFLICT(409)、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 7 个分支（成功/同级重名/无权限/parent不存在/跨租户/非法scope/根下创建）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.4 重命名节点：PATCH /api/resource-trees/{scope}/nodes/{node_id}

### 对照章节
- tech.md §6.2.5.3 PATCH /api/resource-trees/{scope}/nodes/{node_id}（重命名节点）
- architecture.md resource_tree ｜资源树 > API


### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/api/serializers.py`
- `src/apps/resource_tree/services.py`
- `src/apps/resource_tree/tests/*`

### 目标
重命名 folder 或 resource 节点，并保持路径/唯一约束

### 范围
**包含**
- 校验 node 归属
- 更新 name 并处理同级唯一冲突
- 审计：NODE_RENAME

**不包含**
- 不支持改 scope/type

### 接口契约
- URL：PATCH /api/resource-trees/{scope}/nodes/{node_id}
- 入参：{name}
- 权限：RESOURCE_MANAGE
- 错误码：RESOURCE_NODE_NOT_FOUND、NAME_CONFLICT、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（成功/冲突/无权限/not found/跨租户/非法scope）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.5 移动节点：POST /api/resource-trees/{scope}/move

### 对照章节
- tech.md §6.2.5.4 POST /api/resource-trees/{scope}/move（移动节点）
- prd.md §3 核心概念与全局规范（资源树移动）


### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/services.py`
- `src/apps/resource_tree/tests/*`

### 目标
将节点移动到新 parent，并维护 order 与路径

### 范围
**包含**
- 校验 src/dst
- 防循环（不能移入自身子树）
- 更新 parent_node_id/order
- 审计：NODE_MOVE

**不包含**
- 不实现跨 scope 移动

### 接口契约
- URL：POST /api/resource-trees/{scope}/move
- 入参：{node_id,to_parent_node_id,to_index?}
- 权限：RESOURCE_MANAGE
- 错误码：INVALID_MOVE(400)、RESOURCE_NODE_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（成功/移入自身子树/跨租户/node不存在/parent不存在/无权限/冲突/非法scope）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T4.6 同级排序：POST /api/resource-trees/{scope}/reorder

### 对照章节
- tech.md §6.2.5.5 POST /api/resource-trees/{scope}/reorder（同级排序）
- prd.md §3 核心概念与全局规范（排序）


### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/services.py`
- `src/apps/resource_tree/tests/*`

### 目标
同一 parent 下按给定序列重排节点顺序

### 范围
**包含**
- 输入校验（同级节点全集/不缺不重）
- 批量更新 order
- 审计：NODE_REORDER

**不包含**
- 不支持跨 parent reorder

### 接口契约
- URL：POST /api/resource-trees/{scope}/reorder
- 入参：{parent_node_id, ordered_node_ids:[...]}
- 权限：RESOURCE_MANAGE
- 错误码：VALIDATION_*、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（成功/缺失id/重复id/跨租户/无权限/非法scope）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）


## T4.7 删除节点：DELETE /api/resource-trees/{scope}/nodes/{node_id}（含递归/保护规则）

### 对照章节
- tech.md §4 资源树（删除/移动/排序/一致性约束）
- architecture.md resource_tree API 清单（DELETE node）

### 涉及文件
- `src/apps/resource_tree/api/views_tree.py`
- `src/apps/resource_tree/api/serializers.py`
- `src/apps/resource_tree/services.py（delete 递归/检查）`
- `src/apps/resource_tree/selectors.py`
- `src/apps/resource_tree/tests/*`

### 目标
支持删除资源树节点，并保证：
- 文件夹可递归删除（或按约定限制非空不可删）
- 绑定业务对象（dataset/chart/dashboard/flow/...）的节点按规则阻止删除或级联清理

### 范围
**包含**
- 递归删除（含 sort_order 重排）
- 删除前检查：root 不可删、跨 scope 不可删、无权限不可删
- 业务绑定保护：若 node 关联业务对象，返回明确错误码（或触发软删策略，按 tech.md）

**不包含**
- 回收站（软删恢复）能力（后续版本）

### 接口契约
- Method: DELETE
- Path: `/api/resource-trees/{scope}/nodes/{node_id}`
- Response: 200（删除成功）/ 409（被引用/非空不可删）/ 403（无权限）等

### 验收标准（DoD）
- ✅ 单测覆盖：删叶子、删文件夹递归、删 root 拒绝、删被引用节点拒绝、权限拒绝
- ✅ 数据一致性：删除后 siblings 的 sort_order 连续


## T5.1 数据仓库集成基建：DW 连接管理 + SQL 执行器（按租户隔离）

### 对照章节
- tech.md §2.1 系统空间划分与访问边界（DW 在 integrations）
- architecture.md integrations/ 目录设计


### 涉及文件
- `src/integrations/dw/client.py`
- `src/integrations/dw/__init__.py`
- `src/config/settings/base.py（DW 超时/白名单配置，如需要）`
- `src/tests/test_dw_client.py（新增）`

### 目标
提供可复用的 run_sql/query_sql 接口，支持 tenant 级连接参数与超时控制

### 范围
**包含**
- DWClient/ConnectionProvider（按 tenant 获取连接）
- 只读查询与写入/DDL 分离
- 错误映射到统一错误码

**不包含**
- 不引入真实 DW（测试用 sqlite/mock）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（query/run；超时；语法错；连接错；tenant 不存在；注入防护-最小）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T5.2 DW DDL：建表/删表/改表（供 modeling 使用）

### 对照章节
- tech.md §7 建模模块（物理表 DDL 约束）
- prd.md §8 建模模块（Modeling）


### 涉及文件
- `src/integrations/dw/ddl.py`
- `src/integrations/dw/swap.py`
- `src/tests/test_dw_ddl.py（新增）`

### 目标
modeling 创建/删除/变更字段时可调用 DDL 层完成物理表同步

### 范围
**包含**
- create_table、alter_table_add_field、alter_table_update_field、drop_table（按 tech 需要取舍）

**不包含**
- 不做复杂在线迁移（如类型变更大数据回填）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（建表；加字段；删表；重复建表；DDL 失败回滚）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.1 modeling 域模型与迁移：ModelingTable/ModelingField/（可选 Records）

### 对照章节
- tech.md §7.6 API 总览（建模模块完整清单）
- prd.md §8 建模模块（Modeling）
- architecture.md modeling ｜建模 > 模型


### 涉及文件
- `src/apps/modeling/models/table.py`
- `src/apps/modeling/models/field.py`
- `src/apps/modeling/models/record.py（可选）`
- `src/apps/modeling/migrations/*`

### 目标
完成建模元数据表结构，支撑表/字段接口与 DDL 同步

### 范围
**包含**
- ModelingTable（name/key/desc/status/tenant_id）
- ModelingField（table_id/name/key/type/nullable/order/ref?）
- 必要索引/唯一（tenant+key）

**不包含**
- 不实现复杂版本控制（schema versioning）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（建表元数据；加字段；唯一冲突；重排字段）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.2 建模表接口：/api/modeling/tables（GET/POST/GET detail/PATCH/DELETE）+ 资源树挂载

### 对照章节
- tech.md §7.8.1~7.8.5（tables 相关接口）
- tech.md §7.8.1 GET /api/modeling/tables
- prd.md §8 建模模块（表管理）


### 涉及文件
- `src/apps/modeling/api/views_tables.py`
- `src/apps/modeling/api/serializers_tables.py`
- `src/apps/modeling/services/tables.py`
- `src/apps/modeling/selectors.py`
- `src/apps/modeling/api/permissions.py`
- `src/apps/modeling/api/urls.py`
- `src/apps/resource_tree/services.py（挂载节点）`
- `src/apps/modeling/tests/*`

### 目标
完成 tables CRUD，并在创建/删除时联动 DW DDL 与资源树节点

### 范围
**包含**
- tables list/create/detail/update/delete
- 创建：写 metadata → 创建 DW 物理表 → 创建资源树节点（scope=TABLE）
- 删除：校验引用（datasets/charts/flows）→ 删除 DW 表 → 删除节点
- 审计：TABLE_*

**不包含**
- 不实现“软删除 + 可恢复”（除非 tech/PRD 明确）

### 接口契约
- URL：
  - GET /api/modeling/tables（分页）
  - POST /api/modeling/tables
  - GET/PATCH/DELETE /api/modeling/tables/{table_id}
- 权限：TABLE_MANAGE
- 错误码：TABLE_NOT_FOUND、TABLE_KEY_CONFLICT(409)、DW_DDL_FAILED(500)、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（CRUD + DDL 失败回滚 + 资源树创建失败补偿 + 冲突 + 无权限）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.3 建模字段接口：/api/modeling/tables/{table_id}/fields（GET/POST/PATCH/DELETE）+ reorder

### 对照章节
- tech.md §7.8.6~7.8.10（fields 相关接口）
- prd.md §8 建模模块（字段管理与排序）


### 涉及文件
- `src/apps/modeling/api/views_fields.py`
- `src/apps/modeling/api/serializers_fields.py`
- `src/apps/modeling/services/fields.py`
- `src/apps/modeling/selectors.py`
- `src/apps/modeling/tests/*`
- `src/integrations/dw/ddl.py（字段 DDL）`

### 目标
可管理字段并同步 DW schema，支持字段排序

### 范围
**包含**
- 字段列表/创建/更新/删除
- 字段排序 reorder
- DDL 同步（按允许的变更类型）
- 审计：FIELD_*

**不包含**
- 不做危险类型变更（如 int→json）除非 tech 明确允许

### 接口契约
- URL：GET/POST /api/modeling/tables/{table_id}/fields；PATCH/DELETE /api/modeling/tables/{table_id}/fields/{field_id}；POST /api/modeling/tables/{table_id}/fields/reorder
- 权限：TABLE_MANAGE
- 错误码：TABLE_NOT_FOUND、FIELD_NOT_FOUND、DW_DDL_FAILED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（CRUD+reorder+非法输入+DDL失败+无权限+跨表 field_id）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.4 引用候选：GET /api/modeling/tables/{ref_table_id}/reference-candidates

### 对照章节
- tech.md §7.8.11 GET /api/modeling/tables/{ref_table_id}/reference-candidates
- prd.md §8 建模模块（外键/引用）


### 涉及文件
- `src/apps/modeling/api/views_reference.py`
- `src/apps/modeling/api/serializers_reference.py`
- `src/apps/modeling/selectors.py`
- `src/apps/modeling/tests/*`

### 目标
返回可作为引用字段的候选（按字段类型/唯一性规则）

### 范围
**包含**
- 基于 modeling 元数据筛选候选字段
- 必要时查询 DW 统计（可选）

**不包含**
- 不做复杂推荐排序（除非 tech 要求）

### 接口契约
- URL：GET /api/modeling/tables/{ref_table_id}/reference-candidates
- 权限：TABLE_MANAGE
- 错误码：TABLE_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（正常/无候选/table不存在/无权限/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.5 数据查询：POST /api/modeling/tables/{table_id}/data/query（走 QueryEngine）

### 对照章节
- tech.md §7.8.12 POST /api/modeling/tables/{table_id}/data/query
- tech.md §6.3 查询引擎（Query Engine）
- prd.md §8 建模模块（数据预览/查询）


### 涉及文件
- `src/apps/modeling/api/views_records.py（或 views_tables.py 内）`
- `src/apps/modeling/api/serializers_records.py`
- `src/apps/query_engine/services.py`
- `src/apps/modeling/tests/*`

### 目标
对建模表执行查询（分页/排序/过滤），输出统一格式结果

### 范围
**包含**
- 将请求转成 QueryDSL → QueryEngine.run
- 应用列/行权限（若要求）

**不包含**
- 不实现导出（导出走 query/export 或 reports/export）

### 接口契约
- URL：POST /api/modeling/tables/{table_id}/data/query
- 入参：QueryDSL（按 tech/prd）
- 权限：TABLE_READ
- 错误码：QUERY_INVALID(400)、PERMISSION_DENIED、TABLE_NOT_FOUND

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（正常分页/非法dsl/列权限裁剪/行权限叠加/无权限/table不存在/超时）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T6.6 记录 CRUD：/api/modeling/tables/{table_id}/records（创建/更新/删除/批量删可选）

### 对照章节
- tech.md §7.8.13~7.8.17（records 相关接口）
- prd.md §8 建模模块（记录管理，若在 scope）


### 涉及文件
- `src/apps/modeling/api/views_records.py`
- `src/apps/modeling/api/serializers_records.py`
- `src/apps/modeling/services/records.py（新增）`
- `src/integrations/dw/client.py（写入/事务）`
- `src/apps/modeling/tests/*`

### 目标
支持对建模表记录进行增改删与查询单条（按 tech 约定）

### 范围
**包含**
- GET 单条 record
- POST 创建
- PATCH 更新
- DELETE 删除
- 可选：batch-delete

**不包含**
- 不实现复杂事务批量写入（如批量 upsert）

### 接口契约
- URL：GET /api/modeling/tables/{table_id}/records/{record_id}；POST /api/modeling/tables/{table_id}/records；PATCH/DELETE /api/modeling/tables/{table_id}/records/{record_id}；POST /api/modeling/tables/{table_id}/records/batch-delete（可选）
- 权限：TABLE_WRITE
- 错误码：RECORD_NOT_FOUND、VALIDATION_*、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（CRUD + 列权限写拒绝 + 类型错 + 不存在 + 无权限 + batch-delete 可选）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T7.1 统一 FilterDSL：schema + validator + compiler（AST→SQL）

### 对照章节
- tech.md §6.3 查询引擎（QueryBuilder/Runner）
- prd.md §4 统一查询 DSL & 权限模型（横切关注）
- architecture.md query_engine ｜查询引擎 > Services


### 涉及文件
- `src/common/dsl/filter_schema.py`
- `src/common/dsl/validator.py`
- `src/common/dsl/compiler/ast.py`
- `src/common/dsl/compiler/sql.py`
- `src/apps/query_engine/compiler/*（如有）`
- `src/apps/query_engine/tests/*`

### 目标
给定 FilterDSL 能完成结构校验并编译为安全 SQL（参数化）

### 范围
**包含**
- 定义 DSL schema（字段/操作符/类型）
- validator（结构/字段存在/类型匹配）
- compiler（AST→SQL + params）

**不包含**
- 不做跨表 join 推导（如需 join，由后续 QueryBuilder 任务实现）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 15 个分支（所有操作符 + 类型不匹配 + 未知字段 + 嵌套 AND/OR/NOT）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T7.2 QueryBuilder：将 Dataset/Chart 的 QuerySpec 编译为 SQL（含行列权限叠加）

### 对照章节
- tech.md §6.3 查询引擎（QueryBuilder/Runner）
- prd.md §10 数据集（Datasets）


### 涉及文件
- `src/apps/query_engine/services.py`
- `src/apps/query_engine/compiler/*`
- `src/apps/iam/selectors.py（读取行列权限）`
- `src/common/dsl/compiler/sql.py`
- `src/apps/query_engine/tests/*`

### 目标
输入 QuerySpec（维度/指标/排序/分页/过滤）输出 SQL+params，并叠加 row/column 权限

### 范围
**包含**
- select 列裁剪（ColumnPermission）
- where 叠加（业务过滤 + RowPermission）
- limit/offset/order by
- 聚合/分组（按 PRD/tech）

**不包含**
- 不实现复杂窗口函数（除非 PRD 明确）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（select裁剪/where叠加/聚合/排序/分页/权限边界）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T7.3 查询校验：POST /api/query/validate（校验并预编译）

### 对照章节
- tech.md §6.3.5.2 POST /api/query/validate（校验并预编译）
- tech.md §6.3.5 接口规范（查询引擎）
- prd.md §4 统一查询 DSL


### 涉及文件
- `src/apps/query_engine/api/views.py（新增）`
- `src/apps/query_engine/api/serializers.py（新增）`
- `src/apps/query_engine/api/urls.py（新增）`
- `src/apps/query_engine/services.py`
- `src/apps/query_engine/tests/*`

### 目标
对请求 QuerySpec 做校验并返回编译结果摘要（不执行）

### 范围
**包含**
- 调用 validator+builder 返回 warnings/compiled_meta（按 tech）

**不包含**
- 不返回完整 SQL（除非 tech 允许；避免泄露）

### 接口契约
- URL：POST /api/query/validate
- 入参：QuerySpec
- 权限：与资源 READ 权限一致（dataset/table/chart）
- 错误码：QUERY_INVALID(400)、PERMISSION_DENIED(403)

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（合法/非法dsl/未知字段/权限不足/跨租户/空指标/聚合冲突/排序非法）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T7.4 执行查询：POST /api/query/run（执行并返回结果集）

### 对照章节
- tech.md §6.3.5.3 POST /api/query/run（执行查询）
- tech.md §6.3.5 接口规范（查询引擎）
- prd.md §11 可视化查询（Charts / 探索分析）


### 涉及文件
- `src/apps/query_engine/api/views.py`
- `src/apps/query_engine/api/serializers.py`
- `src/apps/query_engine/runner/runner.py`
- `src/integrations/dw/client.py`
- `src/apps/query_engine/tests/*`

### 目标
执行 QuerySpec 并返回分页结果（rows+columns+total）

### 范围
**包含**
- 调用 builder → dw client 执行
- 返回 columns schema 与 rows
- 支持分页与超时

**不包含**
- 不实现流式返回

### 接口契约
- URL：POST /api/query/run
- 入参：QuerySpec
- 出参：{columns:[...], rows:[...], total:int}
- 错误码：QUERY_INVALID、DW_QUERY_FAILED(500)、TIMEOUT(504)、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（分页/limit cap/超时/语法错/权限裁剪/total计算/空结果/聚合）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T7.5 导出 CSV：POST /api/query/export/csv（异步 ExportJob）

### 对照章节
- tech.md §6.3.5.4 POST /api/query/export/csv（导出 CSV）
- tech.md §6.3.5.4（导出 CSV）
- prd.md §11 可视化查询（导出）


### 涉及文件
- `src/apps/query_engine/api/views.py`
- `src/apps/query_engine/api/serializers.py`
- `src/apps/reports/models/export_job.py（或 src/apps/reports/models/export_job.py）`
- `src/apps/reports/services/exports.py`
- `src/apps/execution/models/task_run.py（使用 TaskRunInstance）`
- `src/apps/query_engine/tests/*`

### 目标
创建导出任务并返回 export_job_id，后台生成文件（或预留）

### 范围
**包含**
- 创建 ExportJob 记录
- 触发异步任务（Celery）
- 状态流转：PENDING/RUNNING/SUCCESS/FAILED

**不包含**
- 不实现文件存储到 OSS（可先本地存储或占位）

### 接口契约
- URL：POST /api/query/export/csv
- 入参：QuerySpec
- 出参：{export_job_id,status}
- 错误码：QUERY_INVALID、PERMISSION_DENIED、EXPORT_CREATE_FAILED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（创建job/无权限/非法dsl/后台执行成功/失败/取消-可不做/大数据限制）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.1 reports 域模型与迁移：Dataset/Chart/Dashboard/DashboardItem/ExportJob/RefreshRun

### 对照章节
- tech.md §9 数据集/图表/仪表盘/导出 接口章节
- prd.md §10 数据集（Datasets）
- architecture.md reports ｜报表与资产（datasets/charts/dashboards） > 模型


### 涉及文件
- `src/apps/reports/models/dataset.py`
- `src/apps/reports/models/chart.py`
- `src/apps/reports/models/dashboard.py`
- `src/apps/reports/models/refresh_run.py`
- `src/apps/reports/models/export_job.py`
- `src/apps/reports/migrations/*`

### 目标
完成报表资产相关表结构，支撑后续接口

### 范围
**包含**
- Dataset（source, base_filter, columns 等）
- Chart（spec, dataset_id 等）
- Dashboard/DashboardItem（layout）
- ExportJob/RefreshRun（状态机）

**不包含**
- 不实现复杂版本历史

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（创建dataset/chart/dashboard/exportjob/refreshrun）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.2 Datasets CRUD：/api/datasets（GET/POST/GET detail/PATCH）+ 资源树挂载

### 对照章节
- tech.md §9.3.6.1~9.3.6.4
- tech.md §9.3.6.1 GET /api/datasets
- prd.md §10 数据集（Datasets）


### 涉及文件
- `src/apps/reports/api/views_datasets.py`
- `src/apps/reports/api/serializers_datasets.py`
- `src/apps/reports/services/datasets.py`
- `src/apps/reports/selectors.py`
- `src/apps/resource_tree/services.py（挂载节点）`
- `src/apps/reports/tests/*`

### 目标
可创建/编辑/查询 Dataset，并挂载到资源树

### 范围
**包含**
- list/create/detail/update
- FilterDSL 校验
- 资源树节点创建（scope=DATASET）
- 审计：DATASET_*

**不包含**
- 不实现删除（若 tech/PRD 未提供 delete）

### 接口契约
- URL：GET/POST /api/datasets；GET/PATCH /api/datasets/{dataset_id}
- 权限：DATASET_MANAGE
- 分页：list
- 错误码：DATASET_NOT_FOUND、NAME_CONFLICT、VALIDATION_*、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（CRUD + filter校验 + 资源树挂载 + 冲突 + 无权限）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.3 Dataset 启用/禁用：POST /api/datasets/{dataset_id}/enable（以及 disable 若 tech 有）

### 对照章节
- tech.md §9.3.6.5 POST /api/datasets/{dataset_id}/enable
- prd.md §10 数据集（启停）


### 涉及文件
- `src/apps/reports/api/views_datasets.py`
- `src/apps/reports/api/serializers_datasets.py`
- `src/apps/reports/services/datasets.py`
- `src/apps/reports/tests/*`

### 目标
可切换 dataset.enabled 状态，并影响下游 charts/dashboards（只读约束）

### 范围
**包含**
- enable endpoint（按 tech）
- 必要时实现 disable（若 tech/PRD 提供）
- 审计：DATASET_ENABLE/DISABLE

**不包含**
- 不实现级联更新 chart/dashboard（除非 PRD 要求强制）

### 接口契约
- URL：POST /api/datasets/{dataset_id}/enable
- 权限：DATASET_MANAGE
- 错误码：DATASET_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（enable/重复enable/not found/无权限/禁用后行为）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.4 Dataset Refresh：POST /api/datasets/{dataset_id}/refresh + GET refresh-runs

### 对照章节
- tech.md §9.3.6.6 POST /api/datasets/{dataset_id}/refresh
- tech.md §9.3.6.7 GET /api/datasets/{dataset_id}/refresh-runs
- prd.md §10 数据集（刷新）


### 涉及文件
- `src/apps/reports/api/views_datasets.py`
- `src/apps/reports/api/serializers_datasets.py`
- `src/apps/reports/services/datasets.py`
- `src/apps/reports/workers/dataset_refresh.py`
- `src/apps/execution/registry/tasks.py（注册 task_type）`
- `src/apps/execution/models/task_run.py`
- `src/apps/reports/tests/*`

### 目标
触发 dataset refresh 并可查询 refresh 运行记录

### 范围
**包含**
- 创建 RefreshRun 记录
- 触发异步任务（可占位）
- refresh-runs 列表分页

**不包含**
- 不实现真实 ETL（若 PRD 未要求；可先标记为预留）

### 接口契约
- URL：POST /api/datasets/{dataset_id}/refresh；GET /api/datasets/{dataset_id}/refresh-runs
- 权限：DATASET_MANAGE
- 错误码：DATASET_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（触发/重复触发/查询runs/无权限/not found/异步失败/状态流转）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.5 Dataset Preview：POST /api/datasets/{dataset_id}/preview（走 QueryEngine）

### 对照章节
- tech.md §9.3.6.8 POST /api/datasets/{dataset_id}/preview
- prd.md §10 数据集（预览）


### 涉及文件
- `src/apps/reports/api/views_datasets.py`
- `src/apps/reports/api/serializers_datasets.py`
- `src/apps/query_engine/services.py`
- `src/apps/reports/tests/*`

### 目标
对 dataset 执行预览查询（分页/排序/过滤）并返回 rows

### 范围
**包含**
- 从 dataset 生成 QuerySpec
- 调用 QueryEngine.run
- 应用 dataset base_filter 与权限

**不包含**
- 不实现导出

### 接口契约
- URL：POST /api/datasets/{dataset_id}/preview
- 权限：DATASET_READ
- 错误码：DATASET_NOT_FOUND、QUERY_INVALID、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（正常/非法filter/列裁剪/行叠加/无权限/not found/limit cap）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.6 Charts：POST /api/charts/preview + Charts CRUD（/api/charts）

### 对照章节
- tech.md §9.4.5.1~9.4.5.6
- tech.md §9.4.5.1 POST /api/charts/preview
- prd.md §11 可视化查询（Charts）


### 涉及文件
- `src/apps/reports/api/views_charts.py`
- `src/apps/reports/api/serializers_charts.py`
- `src/apps/reports/services/charts.py`
- `src/apps/query_engine/services.py`
- `src/apps/reports/tests/*`

### 目标
支持图表预览与图表资产 CRUD（挂载资源树）

### 范围
**包含**
- preview：生成 QuerySpec 并调用 QueryEngine.run
- charts list/create/detail/update/delete
- 资源树节点（scope=CHART）
- 审计：CHART_*

**不包含**
- 不实现图表渲染图片（前端负责）

### 接口契约
- URL：POST /api/charts/preview；GET/POST /api/charts；GET/PATCH/DELETE /api/charts/{chart_id}
- 权限：CHART_MANAGE（CRUD）/CHART_READ（preview）
- 错误码：CHART_NOT_FOUND、DATASET_NOT_FOUND、QUERY_INVALID、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 14 个分支（preview/CRUD/资源树/无权限/not found/非法spec/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.7 Chart 导出：POST /api/charts/{chart_id}/exports + GET /api/exports/{export_job_id}

### 对照章节
- tech.md §9.6.2.1~9.6.2.2
- tech.md §9.6.2.1 POST /api/charts/{chart_id}/exports
- prd.md §11 可视化查询（导出）


### 涉及文件
- `src/apps/reports/api/views_exports.py`
- `src/apps/reports/api/serializers_exports.py`
- `src/apps/reports/services/exports.py`
- `src/apps/reports/workers/export_job.py`
- `src/integrations/storage/client.py`
- `src/apps/execution/registry/tasks.py`
- `src/apps/reports/tests/*`

### 目标
创建图表导出任务并可查询导出状态/下载信息

### 范围
**包含**
- 创建 ExportJob
- 触发异步导出（可先生成 CSV）
- 查询 export job

**不包含**
- 不实现复杂权限分享链接

### 接口契约
- URL：POST /api/charts/{chart_id}/exports；GET /api/exports/{export_job_id}
- 权限：CHART_READ
- 错误码：CHART_NOT_FOUND、EXPORT_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（创建job/查询/无权限/not found/异步成功/失败/limit）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.8 Dashboards CRUD：/api/dashboards（GET/POST/GET detail/PATCH）

### 对照章节
- tech.md §9.5.3.1~9.5.3.4
- tech.md §9.5.3.3 GET /api/dashboards/{dashboard_id}
- prd.md §12 仪表盘（Dashboards）


### 涉及文件
- `src/apps/reports/api/views_dashboards.py`
- `src/apps/reports/api/serializers_dashboards.py`
- `src/apps/reports/services/dashboards.py`
- `src/apps/reports/tests/*`

### 目标
支持 dashboard 资产 CRUD，并挂载资源树

### 范围
**包含**
- list/create/detail/update
- 资源树节点（scope=DASHBOARD）
- 审计：DASHBOARD_*

**不包含**
- 不实现服务端 render（tech.md §9.5.3.8 明确不提供）

### 接口契约
- URL：GET/POST /api/dashboards；GET/PATCH /api/dashboards/{dashboard_id}
- 权限：DASHBOARD_MANAGE
- 错误码：DASHBOARD_NOT_FOUND、NAME_CONFLICT、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（CRUD/资源树/无权限/not found/冲突/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T8.9 Dashboard Items & Layout：items 增删改 + PUT layout

### 对照章节
- tech.md §9.5.3.5~9.5.3.7（以及 X 条目）
- prd.md §12 仪表盘（布局与组件）


### 涉及文件
- `src/apps/reports/api/views_dashboards.py`
- `src/apps/reports/api/serializers_dashboards.py`
- `src/apps/reports/services/dashboards.py`
- `src/apps/reports/tests/*`

### 目标
支持新增/删除/更新 dashboard item，并可更新 layout

### 范围
**包含**
- POST items（新增）
- PATCH items（更新）
- DELETE items（删除）
- PUT layout（整体布局）
- 审计：DASHBOARD_ITEM_*

**不包含**
- 不实现复杂拖拽算法（仅保存布局数据）

### 接口契约
- URL：POST /api/dashboards/{dashboard_id}/items；PATCH/DELETE /api/dashboards/{dashboard_id}/items/{dashboard_item_id}；PUT /api/dashboards/{dashboard_id}/layout
- 权限：DASHBOARD_MANAGE
- 错误码：DASHBOARD_NOT_FOUND、ITEM_NOT_FOUND、CHART_NOT_FOUND（若引用图表）、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（增删改/布局/无权限/not found/引用不存在/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.1 flows 域模型与迁移：Flow/FlowGraph/Schedule/FlowRun/NodeRun/Logs

### 对照章节
- tech.md §8.6 API 总览（Flow 模块完整清单）
- prd.md §9 任务流模块（Flows）
- architecture.md flows ｜任务流 > 模型


### 涉及文件
- `src/apps/flows/models/flow.py`
- `src/apps/flows/models/flow_graph.py`
- `src/apps/flows/models/schedule.py`
- `src/apps/flows/models/flow_run.py`
- `src/apps/flows/models/node_run.py`
- `src/apps/flows/models/run_log.py`
- `src/apps/flows/migrations/*`

### 目标
完成 Flow 与运行态相关表结构与迁移，支撑后续运行与日志接口

### 范围
**包含**
- Flow（name/status/desc/tenant_id）
- FlowGraph（json/dag 版本）
- FlowSchedule（cron/enable）
- FlowRun/FlowNodeRun（状态机、开始结束时间、错误信息）
- 日志存储模型（按 tech：文本/片段/存储引用）

**不包含**
- 不实现复杂历史版本对比 UI（仅存必要字段）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（flow创建/graph保存/schedule保存/run创建/node_run创建/log写入）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.2 Flow CRUD：/api/flows（GET/POST/GET detail/PATCH/DELETE）+ 资源树挂载

### 对照章节
- tech.md §8.7.1~8.7.5
- tech.md §8.7.1 GET /api/flows
- prd.md §9 任务流模块（Flows）


### 涉及文件
- `src/apps/flows/api/views_flows.py`
- `src/apps/flows/api/serializers_flows.py`
- `src/apps/flows/services/flows.py`
- `src/apps/resource_tree/services.py（挂载节点）`
- `src/apps/flows/tests/*`

### 目标
完成 Flow 资产 CRUD，并挂载资源树（scope=FLOW）

### 范围
**包含**
- list/create/detail/update/delete
- 创建资源树节点
- 审计：FLOW_*

**不包含**
- 不实现复制/导入导出

### 接口契约
- URL：GET/POST /api/flows；GET/PATCH/DELETE /api/flows/{flow_id}
- 权限：FLOW_MANAGE
- 错误码：FLOW_NOT_FOUND、NAME_CONFLICT、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（CRUD/资源树/无权限/not found/冲突/运行中禁止删）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.3 Flow Graph：GET/PUT /api/flows/{flow_id}/graph（保存 DAG）

### 对照章节
- tech.md §8.7.6~8.7.7
- tech.md §8.7.6 GET /api/flows/{flow_id}/graph
- prd.md §9 任务流模块（DAG/节点配置）


### 涉及文件
- `src/apps/flows/api/views_flows.py`
- `src/apps/flows/api/serializers_graphs.py`
- `src/apps/flows/services/graphs.py`
- `src/apps/flows/tests/*`

### 目标
可读取/保存 flow graph，保存时做结构校验并生成可执行 DAG

### 范围
**包含**
- GET 返回 graph
- PUT 保存 graph
- 校验：无环、节点引用合法、必填字段

**不包含**
- 不实现可视化布局算法（前端负责保存 layout 字段）

### 接口契约
- URL：GET/PUT /api/flows/{flow_id}/graph
- 权限：FLOW_MANAGE
- 错误码：FLOW_NOT_FOUND、FLOW_INVALID_DAG(400)、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（合法/非法/无权限/flow不存在/环检测/节点缺字段/引用不存在）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.4 Flow Validate：POST /api/flows/{flow_id}/validate（校验可运行）

### 对照章节
- tech.md §8.7.8 POST /api/flows/{flow_id}/validate
- prd.md §9 任务流模块（校验）


### 涉及文件
- `src/apps/flows/api/views_flows.py`
- `src/apps/flows/api/serializers_graphs.py`
- `src/apps/flows/services/validator.py（新增）`
- `src/apps/flows/tests/*`

### 目标
调用 validate 返回可运行性检查结果（errors/warnings）

### 范围
**包含**
- 复用 graph_validate 输出结构化结果
- 不产生副作用

**不包含**
- 不触发真实执行

### 接口契约
- URL：POST /api/flows/{flow_id}/validate
- 权限：FLOW_MANAGE
- 出参：{valid, errors:[...], warnings:[...]}
- 错误码：FLOW_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（valid/invalid/flow不存在/无权限/无graph/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.5 Flow Schedule：GET/PUT /api/flows/{flow_id}/schedule（cron/启停）

### 对照章节
- tech.md §8.7.9~8.7.10
- tech.md §8.7.9 GET /api/flows/{flow_id}/schedule
- prd.md §9 任务流模块（调度）


### 涉及文件
- `src/apps/flows/api/views_flows.py`
- `src/apps/flows/api/serializers_schedules.py`
- `src/apps/flows/services/schedules.py`
- `src/apps/flows/tests/*`

### 目标
可配置 cron 与 enable 状态，并为调度器提供可拉取配置

### 范围
**包含**
- GET schedule
- PUT schedule（cron 校验）
- 审计：FLOW_SCHEDULE_UPDATE

**不包含**
- 不实现完整调度器（可先提供 Celery beat 或预留）

### 接口契约
- URL：GET/PUT /api/flows/{flow_id}/schedule
- 权限：FLOW_MANAGE
- 错误码：FLOW_NOT_FOUND、CRON_INVALID(400)、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（GET/PUT/非法cron/无权限/flow不存在/enable切换/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.6 触发运行与运行列表：POST/GET /api/flows/{flow_id}/runs（防重复运行）

### 对照章节
- tech.md §8.7.11~8.7.12
- tech.md §8.7.11 POST /api/flows/{flow_id}/runs
- prd.md §9 任务流模块（运行）


### 涉及文件
- `src/apps/flows/api/views_runs.py`
- `src/apps/flows/api/serializers_runs.py`
- `src/apps/flows/services/runs.py`
- `src/apps/flows/tests/*`

### 目标
触发 run 创建 FlowRun/NodeRun，并可分页查询 runs

### 范围
**包含**
- POST trigger：创建 run，初始化 node runs，提交到执行队列
- GET list runs（分页）
- 审计：FLOW_RUN_TRIGGER

**不包含**
- 不实现取消/重跑（若 PRD 未要求）

### 接口契约
- URL：POST /api/flows/{flow_id}/runs；GET /api/flows/{flow_id}/runs
- 权限：FLOW_MANAGE
- 错误码：FLOW_NOT_FOUND、FLOW_INVALID_DAG、FLOW_RUN_ALREADY_RUNNING(409)、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（触发/重复触发/无graph/graph非法/list分页/无权限/tenant suspended/执行注册缺失）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.7 运行态查询：GET /api/flow-runs/{run_id} + node-runs + node-run detail + logs

### 对照章节
- tech.md §8.7.13~8.7.16
- tech.md §8.7.13 GET /api/flow-runs/{run_id}


### 涉及文件
- `src/apps/flows/api/views_runs.py`
- `src/apps/flows/api/serializers_runs.py`
- `src/apps/flows/services/runs.py`
- `src/apps/flows/selectors.py（新增）`
- `src/apps/flows/tests/*`

### 目标
可查询 run 与节点运行明细及日志（分页/分片按 tech）

### 范围
**包含**
- run detail
- node runs list
- node run detail
- run logs

**不包含**
- 不实现 websocket 推送

### 接口契约
- URL：GET /api/flow-runs/{run_id}；GET /api/flow-runs/{run_id}/node-runs；GET /api/flow-node-runs/{node_run_id}；GET /api/flow-runs/{run_id}/logs
- 权限：FLOW_READ
- 错误码：FLOW_RUN_NOT_FOUND、NODE_RUN_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（正常/无权限/not found/跨租户/日志分页/空日志/节点过滤）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T9.8 执行框架：ExecutionRegistry + Celery Worker 执行节点（状态机与重试）

### 对照章节
- prd.md §9 任务流模块（执行/重试/失败策略）
- architecture.md execution ｜执行框架 > Services/API


### 涉及文件
- `src/apps/flows/services/executor.py`
- `src/apps/flows/workers/flow_run.py`
- `src/apps/execution/models/task_run.py（复用底座）`
- `src/apps/execution/registry/tasks.py（注册 flow_run task_type）`
- `src/apps/execution/worker/base.py`
- `src/apps/flows/tests/*`

### 目标
触发 flow run 后，worker 能按 DAG 顺序执行节点并写回状态与日志

### 范围
**包含**
- ExecutionRegistry：按 node.type 路由到 handler
- Celery task：run_flow(run_id) / run_node(node_run_id)
- 状态机：PENDING→RUNNING→SUCCESS/FAILED；失败重试按配置
- 日志写入与截断策略

**不包含**
- 不实现分布式调度优化（只要可跑通）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（简单DAG成功/节点失败/重试/取消-可不做/并发保护/日志写入/handler缺失）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T10.1 audit_logs 域模型与迁移：AuditLog（含 tenant_id + platform 范围）

### 对照章节
- tech.md §10.5~10.9（审计相关）
- prd.md §13 审计日志模块（Audit Logs）
- architecture.md audit_logs ｜审计日志 > 模型


### 涉及文件
- `src/apps/audit_logs/models/audit_log.py`
- `src/apps/audit_logs/migrations/*`

### 目标
完成审计日志表结构，支持按 tenant 与 platform 范围查询

### 范围
**包含**
- AuditLog（action,target_type,target_id,operator,changes,ip,ua,tenant_id?）
- 必要索引（tenant_id+created_at）

**不包含**
- 不实现外部日志投递

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 4 个分支（写入/查询/tenant隔离/platform记录）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T10.2 审计写入器：AuditWriter（内部服务）+ 在关键写操作挂钩

### 对照章节
- tech.md §10.9.1 AuditWriter 接口（内部服务）
- prd.md §13 审计日志模块（记录范围）


### 涉及文件
- `src/apps/audit_logs/writer.py`
- `src/common/audit/emitter.py`
- `src/common/audit/diff.py`
- `各业务写接口的 services.py（按 tech.md 指定的“关键操作”挂钩）`
- `src/apps/audit_logs/tests/*`

### 目标
关键写操作（roles/grants/modeling/flows/reports）都会写审计日志

### 范围
**包含**
- 实现 AuditWriter（写 DB）
- 在 services 层插入审计调用（创建/更新/删除/授权/运行触发）

**不包含**
- 不在本任务实现审计查询 API（下一任务）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（多个模块触发审计/脱敏/写入失败容错）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T10.3 租户审计 API：GET /api/audit-logs + detail + meta/actions + meta/target-types

### 对照章节
- tech.md §10.7.1~10.7.4
- prd.md §13 审计日志模块（租户侧）


### 涉及文件
- `src/apps/audit_logs/api/views_audit_logs.py`
- `src/apps/audit_logs/api/serializers.py`
- `src/apps/audit_logs/api/urls.py`
- `src/apps/audit_logs/selectors.py`
- `src/apps/audit_logs/tests/*`

### 目标
租户用户可按权限查询审计日志列表与详情，并获取 action/type 枚举

### 范围
**包含**
- 列表分页与过滤（按 tech）
- 详情
- meta 枚举接口

**不包含**
- 不做导出

### 接口契约
- URL：GET /api/audit-logs；GET /api/audit-logs/{audit_id}；GET /api/audit-logs/meta/actions；GET /api/audit-logs/meta/target-types
- 权限：AUDIT_READ（或 Owner）
- 错误码：AUDIT_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（list分页/过滤/详情/meta/无权限/not found/跨租户）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T10.4 平台审计 API：GET /api/platform/audit-logs (+ meta) + detail

### 对照章节
- tech.md §10.5.2 平台后台（预留跨租户查询能力）
- tech.md §10.8.1/10.8.2（平台审计 list/detail）
- prd.md §5 平台后台（Platform Admin Console）


### 涉及文件
- `src/apps/audit_logs/api/views_audit_logs.py（平台范围）`
- `src/apps/platform_admin/api/permissions.py（platform_admin 校验）`
- `src/apps/audit_logs/tests/*`

### 目标
平台管理员可跨租户查询审计日志（list/detail/meta）

### 范围
**包含**
- 平台 list/detail
- meta/actions 与 meta/target-types（若前端需要）

**不包含**
- 不提供平台侧写审计（平台写也进入同一表）

### 接口契约
- URL：GET /api/platform/audit-logs；GET /api/platform/audit-logs/{audit_id}；（可选）GET /api/platform/audit-logs/meta/actions；GET /api/platform/audit-logs/meta/target-types
- 权限：is_platform_admin
- 错误码：PERMISSION_DENIED、AUDIT_NOT_FOUND

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（list/detail/meta/非admin/过滤/跨租户可见）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.1 平台后台鉴权与路由分组：/admin/api/*（强制 platform_admin 权限）

### 对照章节
- tech.md §4.6.3 平台后台接口组（必须单独成组）
- prd.md §5 平台后台（Platform Admin Console）
- architecture.md platform_admin ｜平台后台


### 涉及文件
- `src/apps/platform_admin/api/urls.py`
- `src/apps/platform_admin/api/permissions.py`
- `src/api/v1/urls.py（挂载 /admin/api）`

### 目标
/admin/api 下所有接口仅 platform admin 可访问，且不依赖 TenantContext

### 范围
**包含**
- 实现 platform_admin permission class
- admin urls router
- 禁止 tenant_context 强制注入

**不包含**
- 不实现前端页面

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 5 个分支（admin通过/非admin拒绝/无token/tenant header忽略/统一壳）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.2 平台用户列表：GET /admin/api/users（GlobalUser 列表）

### 对照章节
- tech.md §4.8.1 GET /admin/api/users
- prd.md §5 平台后台（用户管理）


### 涉及文件
- `src/apps/platform_admin/api/views_users.py`
- `src/apps/platform_admin/api/serializers_users.py`
- `src/apps/platform_admin/selectors.py`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可分页查询 GlobalUser 列表（支持搜索/过滤按 tech）

### 范围
**包含**
- 分页 list
- 搜索（email/name）
- 字段脱敏（如仅显示必要）

**不包含**
- 不实现导出

### 接口契约
- URL：GET /admin/api/users
- 权限：is_platform_admin
- 分页：统一分页
- 错误码：PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 6 个分支（分页/搜索/非admin/未登录/字段脱敏/空列表）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.3 平台用户管理：GET/PATCH /admin/api/users/{user_id} + enable/disable + reset_password

### 对照章节
- tech.md §4.6.3 平台后台接口组（接口清单）
- prd.md §5 平台后台（用户启停/重置密码）


### 涉及文件
- `src/apps/platform_admin/api/views_users.py`
- `src/apps/platform_admin/api/serializers_users.py`
- `src/apps/platform_admin/services.py`
- `src/apps/accounts/models/users.py（状态字段/密码重置）`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可查看/编辑用户，并可启停与重置密码

### 范围
**包含**
- GET user detail
- PATCH 编辑可编辑字段（按 PRD）
- POST enable/disable
- POST reset_password（生成临时密码或置为随机）

**不包含**
- 不实现邮件通知（可预留）

### 接口契约
- URL：GET/PATCH /admin/api/users/{user_id}；POST /admin/api/users/{user_id}/enable；POST /admin/api/users/{user_id}/disable；POST /admin/api/users/{user_id}/reset_password
- 权限：is_platform_admin
- 错误码：USER_NOT_FOUND、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（get/patch/enable/disable/reset/not found/非admin/禁用后登录失败）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.4 创建租户：POST /admin/api/tenants（创建 tenant + 初始化资源树 root）

### 对照章节
- tech.md §4.8.2 POST /admin/api/tenants
- prd.md §5 平台后台（创建租户）


### 涉及文件
- `src/apps/platform_admin/api/views_tenants.py`
- `src/apps/platform_admin/api/serializers_tenants.py`
- `src/apps/platform_admin/services.py`
- `src/apps/tenants/models/tenant.py`
- `src/apps/resource_tree/models/resource_node.py（root 初始化）`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可创建租户，并完成必要初始化（资源树 root 等）

### 范围
**包含**
- 创建 Tenant
- 初始化 resource_tree roots
- 可选：创建 owner 成员（按 tech）
- 审计：TENANT_CREATE

**不包含**
- 不实现计费/套餐

### 接口契约
- URL：POST /admin/api/tenants
- 权限：is_platform_admin
- 入参：{name, owner_user_ids? 或 emails?（按 tech）}
- 错误码：TENANT_NAME_CONFLICT、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（创建成功/冲突/初始化失败回滚/非admin/参数缺失）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.5 编辑租户：PATCH /admin/api/tenants/{tenant_id}（必须支持改名称）

### 对照章节
- tech.md §4.8.3 PATCH /admin/api/tenants/{tenant_id}
- prd.md §5 平台后台（编辑租户）


### 涉及文件
- `src/apps/platform_admin/api/views_tenants.py`
- `src/apps/platform_admin/api/serializers_tenants.py`
- `src/apps/platform_admin/services.py`
- `src/apps/tenants/models/tenant.py`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可编辑租户名称等字段（至少支持 name）

### 范围
**包含**
- PATCH 更新 name
- 审计：TENANT_UPDATE

**不包含**
- 不实现删除租户

### 接口契约
- URL：PATCH /admin/api/tenants/{tenant_id}
- 权限：is_platform_admin
- 错误码：TENANT_NOT_FOUND、NAME_CONFLICT、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 7 个分支（成功/冲突/not found/非admin/空body）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.6 租户启停：POST /admin/api/tenants/{tenant_id}/enable & /suspend

### 对照章节
- tech.md §4.6.3 平台后台接口清单（enable/suspend）
- prd.md §5 平台后台（启停租户）


### 涉及文件
- `src/apps/platform_admin/api/views_tenants.py`
- `src/apps/platform_admin/services.py`
- `src/apps/tenants/models/tenant.py（状态字段）`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可启用/停用租户；停用后租户侧全部拒绝访问

### 范围
**包含**
- enable/suspend endpoints
- 与 TenantContext 中间件联动
- 审计：TENANT_ENABLE/SUSPEND

**不包含**
- 不实现定时自动启停

### 接口契约
- URL：POST /admin/api/tenants/{tenant_id}/enable；POST /admin/api/tenants/{tenant_id}/suspend
- 权限：is_platform_admin
- 错误码：TENANT_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（enable/suspend/非admin/not found/联动拦截/重复调用幂等）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.7 添加租户成员：POST /admin/api/tenants/{tenant_id}/users（支持批量）

### 对照章节
- tech.md §4.8.4 POST /admin/api/tenants/{tenant_id}/users
- prd.md §5 平台后台（成员管理）


### 涉及文件
- `src/apps/platform_admin/api/views_tenant_users.py`
- `src/apps/platform_admin/api/serializers_tenant_users.py`
- `src/apps/platform_admin/services.py`
- `src/apps/tenants/models/tenant_user.py`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可向租户添加成员（支持批量），并可设置初始角色/owner（按 tech）

### 范围
**包含**
- 支持批量输入（emails 或 user_ids）
- 创建 TenantUser
- 可选：绑定默认角色
- 审计：TENANT_ADD_USER

**不包含**
- 不实现邀请邮件

### 接口契约
- URL：POST /admin/api/tenants/{tenant_id}/users
- 权限：is_platform_admin
- 错误码：TENANT_NOT_FOUND、USER_NOT_FOUND、ALREADY_MEMBER(409)、PERMISSION_DENIED、VALIDATION_*

### 验收标准（DoD）
- ✅ 单测覆盖：至少 12 个分支（批量成功/部分非法输入/重复成员/tenant不存在/非admin/绑定owner/绑定role）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T11.8 租户成员编辑：PATCH /admin/api/tenants/{tenant_id}/users/{tenant_user_id}（及查询）

### 对照章节
- tech.md §4.6.3 平台后台接口清单（tenant users）
- prd.md §5 平台后台（成员编辑/移除）


### 涉及文件
- `src/apps/platform_admin/api/views_tenant_users.py`
- `src/apps/platform_admin/api/serializers_tenant_users.py`
- `src/apps/platform_admin/services.py`
- `src/apps/tenants/models/tenant_user.py`
- `src/apps/platform_admin/tests/*`

### 目标
平台管理员可查询并编辑租户成员状态（启停/移除/owner 等按 PRD）

### 范围
**包含**
- GET tenant users list（若需要）
- PATCH tenant_user
- 可选：remove tenant_user

**不包含**
- 不实现复杂审计回放

### 接口契约
- URL：GET /admin/api/tenants/{tenant_id}/users；PATCH /admin/api/tenants/{tenant_id}/users/{tenant_user_id}
- 权限：is_platform_admin
- 错误码：TENANT_NOT_FOUND、TENANT_USER_NOT_FOUND、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 10 个分支（list/patch/not found/非admin/owner约束/跨tenant）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T12.1 LLM Assist：POST /api/assist/code-suggest（编码/命名建议）

### 对照章节
- tech.md §6.5.2.1 POST /api/assist/code-suggest（编码/命名建议）
- prd.md §3 核心概念与全局规范（AI Assist 若有）
- architecture.md assist ｜LLM Assist


### 涉及文件
- `src/apps/assist/services.py`
- `src/apps/assist/api/views_assist.py`
- `src/apps/assist/api/serializers.py`
- `src/apps/assist/api/urls.py`
- `src/integrations/llm/client.py（新增）`
- `src/integrations/llm/__init__.py（新增）`
- `src/apps/assist/tests/*`

### 目标
输入上下文（代码片段/意图）返回结构化建议（不执行代码）

### 范围
**包含**
- serializer 校验
- 调用 LLM provider（可用 mock/接口封装）
- 限流/超时保护（按 tech）

**不包含**
- 不实现自动改代码提交

### 接口契约
- URL：POST /api/assist/code-suggest
- 权限：已登录
- 入参：{intent, language, snippet, constraints?}
- 出参：{suggestions:[...]}（按 tech）
- 错误码：VALIDATION_*、LLM_TIMEOUT(504)、PERMISSION_DENIED

### 验收标准（DoD）
- ✅ 单测覆盖：至少 8 个分支（正常/超长/超时/mock失败/未登录/参数缺失/限流）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T13.1 API 路由一致性与 Schema 输出：确保 endpoints 与 tech/prd 命名规范一致

### 对照章节
- tech.md §4.6 接口清单（本章范围）


### 涉及文件
- `src/api/v1/urls.py`
- `src/api/v1/schema.py`
- `src/config/urls.py`
- `各 app 的 api/urls.py（最终确认路由挂载）`

### 目标
自动校验路由清单与文档一致，并输出 OpenAPI（或 drf-spectacular schema）

### 范围
**包含**
- 路由遍历校验（缺失/多余/参数命名）
- 生成 schema 并保存到 docs/ 或 artifact

**不包含**
- 不在此任务手工维护超大 YAML（除非你要求）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 1 个全量校验用例（确保路由覆盖率=100%）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T13.2 端到端冒烟测试：登录→切租户→建模建表→建 dataset→chart preview→创建 flow→触发 run

### 对照章节
- prd.md §1.5 使用典型场景（End-to-End 示例）


### 涉及文件
- `src/tests/test_e2e_smoke.py（新增/完善）`
- `src/tests/factories.py（可选）`

### 目标
一条最小 E2E 流程在 CI 中可跑通（使用 sqlite/mock DW）

### 范围
**包含**
- 构造 fixtures
- 跑通核心链路并断言关键返回结构/状态机

**不包含**
- 不要求真实 DW 执行（可 mock）

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ 单测覆盖：至少 1 条完整 E2E + 若干断言（审计写入、资源树挂载、权限生效）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（如涉及模型/字段变更）

## T13.3 质量门禁：lint/format/typecheck/coverage（CI）

### 对照章节
- architecture.md §0. 目标与约束（工程规范）


### 涉及文件
- `.github/workflows/ci.yml（或等价 CI 配置）`
- `pyproject.toml（lint/format/typecheck 配置）`
- `pytest.ini / ruff.toml / mypy.ini（按项目约定）`

### 目标
CI 可执行：lint/format/tests/coverage 并阻止低质量合并

### 范围
**包含**
- 配置 ruff/black/isort/mypy（按项目偏好）
- coverage 阈值（建议）
- pre-commit（可选）

**不包含**
- 不配置复杂部署流水线

### 接口契约
（本任务不涉及对外 HTTP 接口）

### 验收标准（DoD）
- ✅ CI 一键通过：lint + tests + coverage（阈值按你设定）
