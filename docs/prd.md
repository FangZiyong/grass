# 0. 文档信息

* 产品名称（暂定）：多租户配置化数据建模与报表平台
* 版本：V1.0
* 范围：

  * 平台后台（Platform Admin Console）
  * 租户工作区（Tenant Workspace）

    * 建模模块（Modeling）
    * 任务流模块（Flows）
    * 数据集 & 看板模块（Datasets & Boards）
    * 租户内用户 & 角色 & 权限管理（Tenant Settings）

---

# 1. 核心概念与数据实体

## 1.1 GlobalUser（平台用户）

平台级账号，一个 GlobalUser 可以加入多个租户。

| 字段名          | 类型       | 说明                | 校验/约束                  |
| ------------ | -------- | ----------------- | ---------------------- |
| id           | UUID/int | 主键                | 系统生成                   |
| login_name   | string   | 登录名/账号            | 必填；1–50；字母数字下划线；全局唯一   |
| display_name | string   | 显示名称              | 必填；1–50                |
| email        | string   | 邮箱                | 必填；email 格式；可唯一（视业务要求） |
| status       | enum     | ACTIVE / DISABLED | 必填；禁用后阻止登录             |
| created_at   | datetime | 创建时间              | 系统填充                   |
| updated_at   | datetime | 更新时间              | 系统填充                   |

## 1.2 Tenant（租户）

逻辑隔离单位（公司/组织/项目）。

| 字段名        | 类型       | 说明                       | 校验/约束                  |
| ---------- | -------- | ------------------------ | ---------------------- |
| id         | UUID/int | 主键                       |                        |
| code       | string   | 租户编码                     | 必填；1–50；字母数字下划线；全局唯一   |
| name       | string   | 租户名称                     | 必填；1–100               |
| status     | enum     | ACTIVE / SUSPENDED       | 必填；SUSPENDED 表示整个租户被停用 |
| plan       | enum     | BASIC / PRO / ENTERPRISE | 必填；默认 BASIC            |
| created_at | datetime | 创建时间                     |                        |
| updated_at | datetime | 更新时间                     |                        |

## 1.3 TenantUser（租户用户）

GlobalUser 与 Tenant 的关联关系，是权限控制的“人”的主体。

| 字段名        | 类型       | 说明                     | 校验/约束                 |
| ---------- | -------- | ---------------------- | --------------------- |
| id         | UUID/int | 主键                     |                       |
| tenant_id  | 外键       | 所属租户 ID                | 必填；引用 Tenants         |
| user_id    | 外键       | 平台用户 ID（GlobalUser.id） | 必填；引用 GlobalUsers     |
| status     | enum     | ACTIVE / DISABLED      | 必填；仅 ACTIVE 可登录该租户工作区 |
| is_owner   | bool     | 是否该租户 Owner            | 同一租户可有多个 Owner，但必须≥1  |
| last_login | datetime | 最近登录时间                 | 可空                    |
| created_at | datetime | 创建时间                   |                       |
| updated_at | datetime | 更新时间                   |                       |

**约束：**

* `(tenant_id, user_id)` 必须唯一；
* 当租户 status 为 SUSPENDED 时，该租户下所有 TenantUser 不能访问工作区。

## 1.4 Role（租户角色）

租户级角色，用于权限管理。

| 字段名         | 类型       | 说明       | 校验/约束           |
| ----------- | -------- | -------- | --------------- |
| id          | UUID/int | 主键       |                 |
| tenant_id   | 外键       | 所属租户     | 必填              |
| name        | string   | 角色名称     | 必填；1–50；同一租户内唯一 |
| description | string   | 描述       | 可空；0–200        |
| is_system   | bool     | 是否系统内置角色 | 内置角色不可删除        |
| created_at  | datetime | 创建时间     |                 |
| updated_at  | datetime | 更新时间     |                 |

## 1.5 资源与权限

### 1.5.1 Resource（资源）

用户可见的资源类型：

* TABLE（表格，权限拆成 TABLE_SCHEMA & TABLE_DATA 两条）
* FLOW（任务流）
* BOARD（看板）

**资源树：**

每类资源维护独立树结构：

| 字段名          | 类型       | 说明                            |
| ------------ | -------- | ----------------------------- |
| id           | UUID/int | 资源 ID（表/任务流/看板的 ID）           |
| tenant_id    | 外键       | 租户                            |
| type         | enum     | TABLE / FLOW / BOARD / FOLDER |
| parent_id    | UUID/int | 父节点 ID                        |
| display_name | string   | 树节点显示名                        |
| sort_order   | int      | 排序                            |

> FOLDER 类型节点表示目录，不是实际资源；TABLE/FLOW/BOARD 是叶子节点。

### 1.5.2 RolePermission（角色-资源权限）

权限对象绑定的是 Role 与资源（或资源所在文件夹）。

权限级别：

* NONE：无权限
* VIEW：查看
* EDIT：编辑
* MANAGE：管理

字段：

| 字段名           | 类型       | 说明                                       |
| ------------- | -------- | ---------------------------------------- |
| id            | UUID/int | 主键                                       |
| tenant_id     | 外键       | 租户                                       |
| role_id       | 外键       | 角色 ID                                    |
| resource_type | enum     | TABLE_SCHEMA / TABLE_DATA / FLOW / BOARD |
| resource_id   | UUID/int | 资源 ID 或 FOLDER ID                        |
| permission    | enum     | NONE / VIEW / EDIT / MANAGE              |

> 对表结构和表数据分别用 `resource_type = TABLE_SCHEMA` / `TABLE_DATA` + 同一 `resource_id`。

### 1.5.3 行权限 / 列权限

**列权限（ColumnPermission）：**

| 字段名          | 类型       | 说明                            |
| ------------ | -------- | ----------------------------- |
| id           | UUID/int | 主键                            |
| tenant_id    | 外键       | 租户                            |
| role_id      | 外键       | 角色                            |
| table_id     | 外键       | 表 ID                          |
| column_code  | string   | 字段编码                          |
| access_level | enum     | HIDDEN / READONLY / READWRITE |

**行权限（RowPermission）：**

| 字段名         | 类型       | 说明                         |
| ----------- | -------- | -------------------------- |
| id          | UUID/int | 主键                         |
| tenant_id   | 外键       | 租户                         |
| role_id     | 外键       | 角色                         |
| table_id    | 外键       | 表 ID                       |
| rule_name   | string   | 规则名称（可选）                   |
| filter_json | json     | 行过滤条件（使用统一 JSON DSL，详见 2.） |

### 1.5.4 最终权限计算（Effective Permission）

**1）资源级权限（TABLE_SCHEMA / TABLE_DATA / FLOW / BOARD）**

* 对单一角色：

  * 实际权限 = 同一 `resource_type + resource_id` 上，**该表节点配置的权限** 与所有**上级 FOLDER 的默认权限**的最大值（MANAGE > EDIT > VIEW > NONE）。
* 对拥有多个角色的 TenantUser：

  * 对某资源的最终权限 = 所有角色对该资源的权限的**最大值**。

**2）列权限**

对某个 TenantUser：

* 汇总该用户所有角色在 `ColumnPermission` 中的数据；
* 对每列：

  * 可见：存在任一角色对该列不是 HIDDEN；
  * 可写：存在任一角色对该列为 READWRITE；

**3）行权限**

对某个 TenantUser：

* 汇总该用户所有角色在 `RowPermission` 中与该表相关的规则；
* 最终行过滤条件：所有规则的 filter_json 通过 OR 组合：

  * `final_filter = rule1 OR rule2 OR ...`
* 若某角色未配置任何 RowPermission，则该角色对行不增加额外限制（即视为“不过滤”）；
* 若用户有至少一个角色的 TABLE_DATA 权限为 MANAGE，则后端可配置为**不应用 rowFilter**（看到全量数据）。

---

# 2. 统一过滤条件 JSON DSL

用于：

* 任务流中的过滤节点；
* Dataset 基础过滤；
* RowPermission 规则；
* Widget 查询的额外过滤。

## 2.1 DSL 结构

顶层结构：

```json
{
  "op": "and",
  "conditions": [
    { "field": "amount", "operator": ">", "value": 100 },
    {
      "op": "or",
      "conditions": [
        { "field": "status", "operator": "=", "value": "SUCCESS" },
        { "field": "status", "operator": "=", "value": "PARTIAL" }
      ]
    }
  ]
}
```

* 对象可以是：

  * 条件组（有 `op` + `conditions`）；
  * 简单条件（有 `field` / `operator` / `value`）。

### 2.1.1 条件组

| 字段         | 类型         | 说明           |
| ---------- | ---------- | ------------ |
| op         | string     | "and" / "or" |
| conditions | 数组<object> | 子条件或嵌套条件组    |

### 2.1.2 简单条件

| 字段       | 类型     | 说明             |
| -------- | ------ | -------------- |
| field    | string | 字段编码           |
| operator | string | 操作符            |
| value    | any    | 操作值（可标量/数组/对象） |

支持的 operator：

* 通用：`=`, `!=`, `>`, `>=`, `<`, `<=`
* 集合：`in`, `not_in`
* 范围：`between`
* 文本：`contains`, `starts_with`, `ends_with`
* 特殊：`is_null`, `is_not_null`（这两种无需 value）

value 类型要求：

* 对 number 字段：value 必须是 number 或 array<number>；
* 对 string 字段：value 必须是 string 或 array<string>；
* 对 date/datetime：使用 `"YYYY-MM-DD"` / `"YYYY-MM-DD HH:mm:ss"` 字符串表示。

特殊变量：

* CURRENT_USER：当前 TenantUser ID；
* CURRENT_DATE：当前日期；
* CURRENT_DATETIME：当前时间。

---

# 3. 平台后台（Platform Admin Console）

## 3.1 导航结构

* 用户管理（Global Users）
* 租户管理（Tenants）
* 租户成员管理（通过租户详情页查看）
* 审计日志（可后端为主，前端简单列表）

---

## 3.2 GlobalUser 管理

### 3.2.1 GlobalUser 列表页

* 路径：`/admin/users`
* 粒度：每行一个 GlobalUser。

字段：

| 列名   | 类型       | 说明                    | 特殊逻辑          |
| ---- | -------- | --------------------- | ------------- |
| 登录名  | string   | login_name            | 列表支持按登录名搜索    |
| 显示名  | string   | display_name          |               |
| 邮箱   | string   | email                 |               |
| 状态   | enum     | ACTIVE / DISABLED     | 支持在列表筛选       |
| 创建时间 | datetime |                       |               |
| 更新时间 | datetime |                       |               |
| 操作   | -        | 编辑 / 禁用/启用 / （可选重置密码） | 禁用后用户无法登录任何租户 |

校验：

* 搜索输入：支持按登录名/显示名/邮箱模糊匹配；
* 禁用操作必须有确认弹窗。

### 3.2.2 创建 / 编辑 GlobalUser

字段及校验同 1.1 中定义。

行为：

* 创建成功后返回列表；
* 编辑时 login_name 不可修改。

---

## 3.3 租户管理（Tenants）

### 3.3.1 租户列表页

* 路径：`/admin/tenants`
* 粒度：每行一个 Tenant。

字段：

| 列名   | 类型       | 说明                       | 特殊逻辑              |
| ---- | -------- | ------------------------ | ----------------- |
| 租户编码 | string   | code                     | 唯一，点击可进入租户详情/成员管理 |
| 租户名称 | string   | name                     |                   |
| 状态   | enum     | ACTIVE / SUSPENDED       | 列表可筛选             |
| 套餐   | enum     | BASIC / PRO / ENTERPRISE |                   |
| 创建时间 | datetime |                          |                   |
| 更新时间 | datetime |                          |                   |
| 操作   | -        | 编辑 / 启用/停用 / 查看成员        | 停用需弹窗确认           |

### 3.3.2 新建 / 编辑租户

字段同 1.2，约束：

* 新建时 code 唯一；
* 编辑时 code 不可修改；
* 状态变更为 SUSPENDED 时说明“租户用户无法登录，所有任务流调度停用”。

---

## 3.4 TenantUser 管理（平台视角）

### 3.4.1 租户成员列表页

* 路径：`/admin/tenants/:tenantId/users`
* 粒度：每行一个 TenantUser。

字段：

| 列名       | 类型       | 说明                      |
| -------- | -------- | ----------------------- |
| 登录名      | string   | GlobalUser.login_name   |
| 显示名      | string   | GlobalUser.display_name |
| 邮箱       | string   | GlobalUser.email        |
| 状态       | enum     | ACTIVE / DISABLED       |
| 是否 Owner | bool     |                         |
| 角色列表     | string   | 所在租户的角色名称，用逗号分隔         |
| 创建时间     | datetime |                         |
| 更新时间     | datetime |                         |
| 操作       | -        | 编辑状态/Owner / 禁用 / 移出    |

新增成员：

* 通过搜索 GlobalUser 选择；
* 状态默认为 ACTIVE；
* 可选择是否 Owner。

约束：

* `(tenant_id, user_id)` 唯一；
* 至少有一个 Owner（平台端可以提示检查）。

---

# 4. 租户工作区（Tenant Workspace）总览

## 4.1 导航结构（租户前台）

* 建模（Modeling）
* 任务流（Flows）
* 看板（Boards）
* 系统设置（Settings）

  * 租户用户管理
  * 角色管理
  * 权限配置

## 4.2 登录与租户上下文

* 租户用户通过某种方式选择当前租户（由产品整体架构决定）；
* 所有业务接口均携带 `tenant_id`，后端必须按租户隔离数据。

---

# 5. 租户前台：权限与设置

## 5.1 租户用户管理（Settings → Users）

### 5.1.1 列表页

* 路径：`/app/:tenantId/settings/users`
* 粒度：每行一个 TenantUser。

字段：

| 列名       | 类型       | 说明                      |
| -------- | -------- | ----------------------- |
| 登录名      | string   | GlobalUser.login_name   |
| 显示名      | string   | GlobalUser.display_name |
| 邮箱       | string   | GlobalUser.email        |
| 状态       | enum     | ACTIVE / DISABLED       |
| 是否 Owner | bool     |                         |
| 角色列表     | string   | 本租户的角色名列表               |
| 最近登录时间   | datetime | 可空                      |
| 创建时间     | datetime |                         |
| 操作       | -        | 编辑角色 / 禁用/启用（租户内）       |

权限：

* 仅 TenantOwner 或有特定权限的角色可访问该页。

### 5.1.2 编辑 TenantUser 角色

* 弹窗显示角色多选列表；
* 保存后覆盖该 TenantUser 当前角色绑定。

---

## 5.2 角色管理（Settings → Roles）

### 5.2.1 角色列表页

* 路径：`/app/:tenantId/settings/roles`
* 粒度：每行一个 Role。

字段：

| 列名     | 类型       | 说明             |
| ------ | -------- | -------------- |
| 角色名称   | string   | name           |
| 描述     | string   | description    |
| 是否系统内置 | bool     | is_system      |
| 创建时间   | datetime |                |
| 更新时间   | datetime |                |
| 操作     | -        | 编辑 / 删除 / 配置权限 |

约束：

* is_system=true 的角色不可删除。

### 5.2.2 角色编辑表单

字段及校验见 1.4 Role 定义。

---

## 5.3 角色权限配置（Settings → Roles → Permissions）

### 5.3.1 页面结构

* 左侧：资源类型 Tabs：

  * 表格权限
  * 任务流权限
  * 看板权限
* 右侧：

  * 对应资源树 + 权限下拉。

### 5.3.2 表格权限 Tab

* 资源树：表格资源树（FOLDER + TABLE）；
* 选中某表时显示两行：

| 权限项   | 可选值                         |
| ----- | --------------------------- |
| 表结构权限 | NONE / VIEW / EDIT / MANAGE |
| 表数据权限 | NONE / VIEW / EDIT / MANAGE |

文件夹节点：

* 显示“默认表结构权限 / 默认表数据权限”的下拉；
* 未显式配置的子表，默认继承文件夹权限；
* 若表节点有单独配置，则使用表节点配置。

### 5.3.3 任务流权限 Tab

资源树：任务流资源树。

* 每个 Flow 可配置：NONE / VIEW / EDIT / MANAGE；
* 文件夹支持默认权限。

### 5.3.4 看板权限 Tab

资源树：看板资源树。

* 每个 Board 可配置：NONE / VIEW / EDIT / MANAGE；
* 文件夹支持默认权限。

---

## 5.4 表数据的行/列权限配置

在“建模 → 表详情页”中有 Tab："数据权限"。

### 5.4.1 列权限配置 UI

* 上方：角色选择（下拉）；
* 中间：字段列表。

字段列表列：

| 列名   | 类型     | 说明                        |
| ---- | ------ | ------------------------- |
| 字段名  | string | display_name              |
| 字段编码 | string | code（只读）                  |
| 类型   | string | 数据类型                      |
| 列权限  | enum   | HIDDEN/READONLY/READWRITE |

规则：

* 每次保存覆盖该角色在该表上的列权限；
* 未配置的列可默认 READWRITE 或 READONLY（建议默认 READWRITE，仅受资源级 TABLE_DATA 权限约束）。

### 5.4.2 行权限配置 UI

* 上方：角色选择；
* 中间：规则列表（每条规则一个 RowPermission）；
* 每条规则包含：

  * 规则名称（可选）
  * 条件编辑器（使用统一 JSON DSL）；

保存时：

* 序列化为 filter_json，写入 RowPermission 表；
* 删除规则即删除对应记录。

---

# 6. 建模模块（Modeling）

> 负责表结构与表数据；表编码/字段编码由本地 ollama 自动生成。

## 6.1 表格资源树

* 左：表格资源树，节点类型：

  * FOLDER（文件夹）
  * TABLE（表）
* 操作：

  * 新建文件夹：在选中节点下新建子文件夹；
  * 重命名/删除文件夹：禁止删除非空文件夹；需要具备 Manage 权限；
  * 拖动表到不同文件夹：需要对该表 TABLE_SCHEMA = MANAGE。

权限：

* 用户对某表的 TABLE_SCHEMA 和 TABLE_DATA 均为 NONE 时，该表不在树上展示；
* 若文件夹下没有任何用户可见的表，则不显示该文件夹。

---

## 6.2 表列表页

* 选中某个文件夹（或根）后，右侧显示该目录下所有**用户有权限的表**。
* 粒度：每行一张表。

字段：

| 列名   | 类型       | 说明                            |
| ---- | -------- | ----------------------------- |
| 表名   | string   | display_name                  |
| 表编码  | string   | code（只读，由 LLM 自动生成）           |
| 表类型  | enum     | 维度 / 事实 / 配置 / 其他             |
| 创建人  | string   | 创建该表的 TenantUser.display_name |
| 创建时间 | datetime |                               |
| 更新时间 | datetime |                               |
| 操作   | -        | 结构 / 数据 / 数据权限 / 删除           |

按钮权限：

* 结构：TABLE_SCHEMA ≥ VIEW；
* 数据：TABLE_DATA ≥ VIEW；
* 数据权限：TABLE_DATA = MANAGE；
* 删除：TABLE_SCHEMA = MANAGE。

---

## 6.3 新建 / 编辑表

### 6.3.1 新建表表单

字段：

| 字段    | 类型     | 必填 | 说明                        | 校验            |
| ----- | ------ | -- | ------------------------- | ------------- |
| 表名    | string | 是  | 1–50                      | 非空            |
| 表编码   | string | 否  | 自动生成，前端只读显示               | 后端校验唯一且符合命名规则 |
| 表类型   | enum   | 是  | 维度 / 事实 / 配置 / 其他         | 必选            |
| 描述    | string | 否  | 0–200                     |               |
| 所属文件夹 | string | 否  | resource_tree 中 folder_id | 不填则默认根目录      |

**编码生成逻辑（LLM）：**

* 前端在表名 blur 时：

  * 调用 `POST /api/llm/generate_table_code`，参数：

    * display_name
    * tenant_id
* 后端调用本地 ollama：

  * 生成英文小写蛇形编码，如 `order`, `user_profile`；
  * 清洗：小写 + 非字母数字下划线替换为下划线；
  * 若不符合正则或为空，用本地规则 fallback（如拼音）；
  * 检查当前租户唯一性，不唯一则加 `_1` `_2` 后缀。
* 前端将返回的 code 显示为只读字段。

### 6.3.2 编辑表

* 表编码不可修改；
* 表名、表类型、描述可修改；
* 修改表名不影响 code。

**删除表：**

* 前后端检查：

  * 用户 TABLE_SCHEMA = MANAGE；
  * 后端检查依赖：

    * 表是否被任务流节点使用；
    * 表是否被 Dataset / Widget 使用；
    * 表是否在 Relation 中被引用；
  * 有依赖则拒绝删除，返回详细说明。

---

## 6.4 字段管理

### 6.4.1 字段列表页

* Tab 名称：结构
* 粒度：每行一个字段。

字段列表列：

| 列名   | 类型     | 说明                              |
| ---- | ------ | ------------------------------- |
| 字段名  | string | display_name                    |
| 字段编码 | string | code（只读）                        |
| 类型   | enum   | string/int/float/decimal/bool/… |
| 是否主键 | bool   | 用标记或图标显示                        |
| 是否必填 | bool   | not null                        |
| 默认值  | string | 显示为字符串                          |
| 描述   | string |                                 |
| 操作   | -      | 编辑 / 删除（视权限 & 是否系统字段）           |

权限：

* TABLE_SCHEMA ≥ VIEW：仅查看；
* TABLE_SCHEMA ≥ EDIT：可新增/编辑/删除字段；
* 系统字段（is_internal=true）不允许删除，不允许修改 code/type。

### 6.4.2 新建字段表单

字段：

| 字段   | 类型     | 必填 | 说明                           | 校验                            |
| ---- | ------ | -- | ---------------------------- | ----------------------------- |
| 字段名  | string | 是  | 1–50                         | 非空                            |
| 字段编码 | string | 否  | 自动生成，前端只读展示                  | 后端保证唯一 & 命名规则                 |
| 类型   | enum   | 是  | string/int/float/decimal/... | 必选                            |
| 是否主键 | bool   | 否  | 默认 false                     | 若已有主键字段，则禁止继续设置多个主键（V1 限制单主键） |
| 是否必填 | bool   | 否  | 默认 false                     |                               |
| 默认值  | any    | 否  | 按类型输入                        | 前端初步校验类型；后端再严格校验              |
| 描述   | string | 否  | 0–200                        |                               |

字段编码生成逻辑（LLM）：

* 用户填写字段名后，blur 时：

  * 调用 `POST /api/llm/generate_field_code`，参数：

    * display_name
    * table_code
* 后端生成/清洗/唯一性检验类似表编码。

### 6.4.3 字段生命周期规则

* 创建：

  * 写入 meta_fields；
  * 对应物理表执行 `ALTER TABLE ADD COLUMN`（可默认 NULL）。
* 修改：

  * 允许修改：display_name、is_required、default_value、描述；
  * 不允许修改：code、type（避免复杂迁移）。
* 删除：

  * 后端检查依赖：

    * Relation 是否引用；
    * Flow 节点 / Dataset / Widget 是否引用；
  * 有依赖则禁止删除；
  * 无依赖则：

    * 从 meta_fields 删除；
    * 物理表执行 `ALTER TABLE DROP COLUMN`。

---

## 6.5 表数据页

* Tab 名称：数据
* 粒度：每行代表一条记录。

字段：

* 动态生成：用户可见的字段（根据列权限）；
* 列头显示 `display_name`。

操作：

* 查询：

  * 支持简单过滤（前端构造 DSL 或简化参数）；
  * 支持分页、排序（部分字段）。
* 新增行：

  * TABLE_DATA ≥ EDIT；
  * 弹窗表单，展示用户可见的 READWRITE 字段；
* 编辑行：

  * TABLE_DATA ≥ EDIT；
  * 编辑表单中仅允许修改 READWRITE 字段；
* 删除行：

  * TABLE_DATA ≥ EDIT；
  * 每次操作一行，需确认弹窗。

后端查询逻辑：

1. 计算用户最终 TABLE_DATA 权限；
2. 若权限 < VIEW → 返回 403；
3. 获取用户列权限 → 仅 SELECT 可见列；
4. 获取用户行权限 → 组装 rowFilter → 转为 SQL WHERE；
5. 返回数据。

后端修改逻辑：

1. 检查 TABLE_DATA ≥ EDIT；
2. 检查列权限：不可修改 HIDDEN 或 READONLY 列；
3. 执行 INSERT / UPDATE / DELETE。

---

## 6.6 关系管理

* Tab 名称：关系
* 粒度：每行一个 Relation（以当前表为主表或从表）。

字段：

| 列名   | 类型     | 说明                        |
| ---- | ------ | ------------------------- |
| 关系名称 | string | 自定义名称                     |
| 主表   | string | 表名                        |
| 主表字段 | string | 字段 display_name           |
| 从表   | string |                           |
| 从表字段 | string |                           |
| 类型   | enum   | ONE_TO_MANY / MANY_TO_ONE |
| 描述   | string |                           |
| 操作   | -      | 删除                        |

新建关系表单：

* 主表/从表下拉选择；
* 主表字段/从表字段来自字段列表；
* 类型；
* 描述。

校验：

* 主表字段和从表字段类型需兼容；
* 禁止主表=从表（V1 不支持自引用）；
* 同一对表+字段组合不重复。

---

# 7. 任务流模块（Flows）

## 7.1 资源树与列表

* 路径：`/app/:tenantId/flows`
* 左侧：任务流资源树（FOLDER + FLOW）；
* 右侧：选中目录下的任务流列表。

### 7.1.1 任务流列表页

粒度：每行一个 Flow。

字段：

| 列名     | 类型       | 说明                                 |
| ------ | -------- | ---------------------------------- |
| 任务流名称  | string   | name                               |
| 描述     | string   | description                        |
| 调度状态   | enum     | ENABLED / DISABLED                 |
| 最近运行状态 | enum     | SUCCESS / FAILED / RUNNING / NEVER |
| 最近运行时间 | datetime |                                    |
| 创建人    | string   | TenantUser.display_name            |
| 创建时间   | datetime |                                    |
| 操作     | -        | 编辑 / 手动运行 / 调度配置 / 运行记录 / 删除       |

权限：

* FLOW ≥ VIEW：可见并查看；
* FLOW ≥ EDIT：可编辑、手动运行、配置调度；
* FLOW = MANAGE：可删除、移动。

---

## 7.2 任务流编辑画布

* 路径：`/app/:tenantId/flows/:flowId/edit`
* 布局：

  * 左侧：节点组件面板（分组 Source / Transform / Sink）；
  * 中间：DAG 画布；
  * 右侧：配置面板（节点配置 / Flow 配置 Tab）。

### 7.2.1 Flow 基本信息

右侧 “Flow 配置” Tab：

| 字段       | 类型     | 说明                      |
| -------- | ------ | ----------------------- |
| 名称       | string | 1–100                   |
| 描述       | string | 0–500                   |
| 调度状态     | enum   | ENABLED / DISABLED      |
| 调度类型     | enum   | MANUAL / CRON           |
| Cron 表达式 | string | 当类型=CRON 时必填，crontab 格式 |

校验：

* Cron 表达式基本合法性校验；
* 名称非空。

### 7.2.2 DAG 规则

* Source 节点：无输入端口，只允许作为起点；
* Sink 节点：无硬性限制，但语义上应作为终点；
* 同一 Flow 内不允许存在环：

  * 前端连线时检查；
  * 后端保存时再检查。

---

## 7.3 节点类型与配置

以下都在右侧“节点配置”中配置，每个节点都有字段：节点名称（默认类型+序号，可修改）。

### 7.3.1 Source：HTTP API 源

配置字段：

| 字段           | 类型      | 必填 | 说明                         |
| ------------ | ------- | -- | -------------------------- |
| 节点名称         | string  | 是  | 1–100                      |
| URL          | string  | 是  |                            |
| Method       | enum    | 是  | GET / POST                 |
| Headers      | KV 列表   | 否  | 多个 header                  |
| Query Params | KV 列表   | 否  | GET 参数                     |
| Body 类型      | enum    | 否  | JSON / FORM                |
| Body 内容      | JSON/表单 | 否  | 当 Method=POST 时可填          |
| Token 配置     | string  | 否  | 简单 token 头名和 token 值       |
| JSON 路径      | string  | 是  | 列表所在路径，如 `$.data.items[*]` |
| 字段映射         | 列表      | 是  | 源字段名 → 输出字段名 → 类型          |

校验：

* URL 非空且基本格式合法；
* JSON 路径非空；
* 字段映射至少一个字段被保留。

### 7.3.2 Source：MySQL 源

配置字段：

| 字段       | 类型     | 必填 | 说明            |
| -------- | ------ | -- | ------------- |
| 节点名称     | string | 是  |               |
| host     | string | 是  |               |
| port     | int    | 是  |               |
| username | string | 是  |               |
| password | string | 是  |               |
| database | string | 是  |               |
| SQL      | string | 是  | 仅允许 SELECT 语句 |

校验：

* SQL 不能包含 DML/DDL 关键字（DELETE/UPDATE/INSERT/ALTER 等）；
* 提供“测试连接”和“测试查询”按钮 → 调用后端测试。

### 7.3.3 Source：文件（CSV/Excel）

配置字段：

| 字段    | 类型     | 必填 | 说明                   |
| ----- | ------ | -- | -------------------- |
| 节点名称  | string | 是  |                      |
| 文件上传  | file   | 是  | 上传后得到 file_id        |
| 文件类型  | enum   | 是  | CSV / Excel（自动识别或选择） |
| 分隔符   | string | 否  | CSV 时，默认 `,`         |
| 首行为表头 | bool   | 否  | 默认 true              |
| 字段映射  | 列表     | 是  | 源列名 → 输出字段名/类型       |

---

### 7.3.4 Transform：字段选择/重命名

配置字段：

* 从上游 schema 中读取字段列表；
* 表格中每行：

| 列表字段  | 说明            |
| ----- | ------------- |
| 源字段名  | 上游字段名（只读）     |
| 输出字段名 | 可编辑，默认与源字段名一致 |
| 是否保留  | 复选框，控制该字段是否输出 |

---

### 7.3.5 Transform：过滤

配置字段：

* 使用过滤 DSL 的可视化编辑器：

  * 选择字段、操作符、值；
  * 可添加多条条件 AND/OR 组合；
* 保存时存成 DSL JSON。

---

### 7.3.6 Transform：聚合

配置字段：

1. 分组字段：

   * 多选，下拉选择输入 schema 中的字段；
2. 聚合字段：

   * 列表，每行：

     * 字段名（数值型）
     * 聚合函数：sum/avg/count/max/min
     * 输出字段别名。

---

### 7.3.7 Transform：Join

配置字段：

* 左输入节点、右输入节点（系统自动识别）；
* Join 类型：Inner / Left；
* Join 条件列表：

  * 左字段、右字段；
* 输出字段选择：

  * 左/右字段列表：

    * 是否保留；
    * 输出字段名（可指定前缀）。

---

### 7.3.8 Transform：计算字段

配置字段：

* 输入字段列表展示；
* 新增计算字段列表，每行：

| 字段   | 类型     | 说明                             |
| ---- | ------ | ------------------------------ |
| 新字段名 | string | 编码规则同普通字段编码（可复用 LLM，也可手写）      |
| 数据类型 | enum   | int/float/decimal/string/bool  |
| 表达式  | string | 使用简单表达式语法，如 `price * quantity` |

表达式支持：

* 字段名直接引用；
* * * * /；
* 括号；
* 函数：IF、ABS、ROUND 等（由后端实现子集）。

运行时：

* 表达式错误（如 0 除）导致整个节点失败，并返回错误信息。

---

### 7.3.9 Sink：写入内部表

配置字段：

| 字段   | 类型     | 必填 | 说明                       |
| ---- | ------ | -- | ------------------------ |
| 节点名称 | string | 是  |                          |
| 目标表  | string | 是  | 从当前租户表列表中选择              |
| 写入模式 | enum   | 是  | APPEND / TRUNCATE_INSERT |
| 字段映射 | 列表     | 是  | 目标字段 → 源字段               |

校验：

* 当前用户对目标表 `TABLE_DATA >= EDIT`；
* 所有目标必填字段必须有映射；
* 写入模式：

  * APPEND：直接插入；
  * TRUNCATE_INSERT：先清空表再插入（后端执行事务）。

---

### 7.3.10 Sink：写入 HTTP API

配置字段：

| 字段      | 类型     | 必填 | 说明                         |
| ------- | ------ | -- | -------------------------- |
| 节点名称    | string | 是  |                            |
| URL     | string | 是  |                            |
| Method  | enum   | 是  | POST / PUT                 |
| Headers | KV 列表  | 否  |                            |
| Body 模板 | string | 是  | JSON 模板，支持 `{{field}}` 占位符 |
| 批量大小    | int    | 否  | 默认 1，最大 100                |

运行：

* 对每条数据或每批数据替换占位符；
* 发送 HTTP 请求；
* 任意一批失败，则节点失败。

---

## 7.4 运行记录与执行语义

### 7.4.1 运行记录列表

* 路径：`/app/:tenantId/flows/runs`
* 粒度：每行一个 Run。

字段：

| 列名      | 类型       | 说明                                   |
| ------- | -------- | ------------------------------------ |
| Run ID  | string   | 主键                                   |
| 任务流名称   | string   |                                      |
| Flow ID | string   |                                      |
| 触发方式    | enum     | MANUAL / SCHEDULED                   |
| 开始时间    | datetime |                                      |
| 结束时间    | datetime |                                      |
| 状态      | enum     | PENDING / RUNNING / SUCCESS / FAILED |
| 耗时（秒）   | number   | (结束 - 开始)                            |
| 操作      | -        | 查看详情                                 |

### 7.4.2 运行详情页

* 展示：

  * Flow 拓扑只读图；
  * 每个节点的状态、耗时、输入条数、输出条数、错误信息（如有）。

### 7.4.3 执行语义（必须实现）

* 同一 Flow 同一时刻仅允许一个 RUN：

  * 若当前 Flow 有 RUNNING 状态的 Run，再次触发时返回错误提示；
* Flow 执行失败规则：

  * 任意一个节点失败 → 整个 Flow 标记 FAILED；
  * 不做自动重试（用户可手动重跑）；
* 写入内部表节点：

  * 任意一条记录写入失败（类型错误、约束失败等）→ 节点失败 → Flow 失败；
  * 使用事务保障“要么全部插入，要么不插入”；
* 调度：

  * CRON 调度只在 Flow 调度状态=ENABLED 时生效；
  * 租户被 SUSPENDED 时，所有调度停止触发。

---

# 8. 数据集 & 看板模块（Datasets & Boards）

## 8.1 数据集（Dataset）管理

### 8.1.1 数据集列表页

* 路径：`/app/:tenantId/boards/datasets`
* 粒度：每行一个 Dataset。

字段：

| 列名   | 类型       | 说明                      |
| ---- | -------- | ----------------------- |
| 名称   | string   | name                    |
| 绑定表  | string   | 表 display_name          |
| 描述   | string   | description             |
| 创建人  | string   | TenantUser.display_name |
| 创建时间 | datetime |                         |
| 更新时间 | datetime |                         |
| 操作   | -        | 编辑 / 删除                 |

权限：

* 与看板模块一致，建议由拥有某些 BOARD 权限的角色管理；（可实现为 DATASET 也是一种 BOARD 子资源）。

### 8.1.2 新建 / 编辑数据集

字段：

| 字段     | 类型     | 必填 | 说明                             |
| ------ | ------ | -- | ------------------------------ |
| 名称     | string | 是  | 1–100                          |
| 绑定表    | string | 是  | 当前租户的表列表，必须有 TABLE_DATA ≥ VIEW |
| 基础过滤条件 | json   | 否  | 使用过滤 DSL                       |
| 描述     | string | 否  | 0–200                          |

后端查询数据时：

* 会先应用 Dataset 的 base_filter，再叠加 Widget 指定的 filter，再叠加行/列权限。

---

## 8.2 看板（Board）管理

### 8.2.1 看板资源树 & 列表

* 路径：`/app/:tenantId/boards`
* 左侧：看板资源树（FOLDER + BOARD）；
* 右侧：看板列表。

看板列表粒度：

| 列名   | 类型       | 说明                      |
| ---- | -------- | ----------------------- |
| 看板名称 | string   | name                    |
| 描述   | string   | description             |
| 创建人  | string   | TenantUser.display_name |
| 创建时间 | datetime |                         |
| 更新时间 | datetime |                         |
| 操作   | -        | 查看 / 编辑 / 删除            |

权限：

* BOARD ≥ VIEW：可见与查看；
* BOARD ≥ EDIT：可编辑；
* BOARD = MANAGE：可删除、移动、配置权限。

---

## 8.3 看板查看页

* 路径：`/app/:tenantId/boards/:boardId/view`
* 结构：

  * 顶部：看板标题 + 描述；
  * 中部：根据 layout 渲染 Widgets（网格布局）。

Widget 取数逻辑：

* 前端逐个调用 `/api/boards/widgets/:widgetId/data`；
* 后端根据：

  * widget.dataset_id；
  * widget.query_config；
  * dataset.base_filter；
  * 表对应的行权限 / 列权限；
* 构造 SQL，并返回数据。

---

## 8.4 看板编辑器

* 路径：`/app/:tenantId/boards/:boardId/edit`
* 布局：

  * 左侧：组件库（Widget 类型列表）；
  * 中间：看板画布（支持拖拽布局，记录 x,y,w,h）；
  * 右侧：选中组件的配置面板。

### 8.4.1 组件类型

* MetricCard（指标卡）
* Chart（折线、柱状、饼）
* Table（数据表格）

### 8.4.2 Widget 通用字段

| 字段名          | 类型       | 说明                          |
| ------------ | -------- | --------------------------- |
| id           | string   | 主键                          |
| board_id     | string   | 所属看板                        |
| tenant_id    | string   | 租户                          |
| type         | enum     | METRIC_CARD / CHART / TABLE |
| title        | string   | 标题                          |
| description  | string   | 描述                          |
| dataset_id   | string   | 所用数据集 ID                    |
| query_config | json     | 查询配置                        |
| viz_config   | json     | 可视化配置（图表为主）                 |
| layout       | json     | {x, y, w, h, zIndex}        |
| created_at   | datetime |                             |
| updated_at   | datetime |                             |

---

## 8.5 Widget 配置规范（重点）

### 8.5.1 MetricCard

`query_config` 示例：

```json
{
  "dataset_id": "ds_123",
  "aggregation": {
    "field": "amount",
    "operator": "sum"
  },
  "filter": {
    "op": "and",
    "conditions": [
      { "field": "date", "operator": ">=", "value": "2025-01-01" }
    ]
  }
}
```

规则：

* `aggregation.field` 必须是数值型字段；
* `operator` 支持 sum/avg/count/max/min。

前端配置 UI：

* 选择数据集；
* 维度字段不需要，直接选指标字段+聚合方式；
* 过滤条件使用 DSL 编辑器。

---

### 8.5.2 Chart

`query_config` 示例：

```json
{
  "dataset_id": "ds_123",
  "chart_type": "line",          // 或 "bar", "pie"
  "dimensions": ["date"],        // X 轴维度
  "metrics": [
    { "field": "amount", "operator": "sum", "alias": "total_amount" }
  ],
  "series_field": "channel",     // 可选，多系列时用
  "filter": {
    "op": "and",
    "conditions": [
      { "field": "date", "operator": ">=", "value": "2025-01-01" }
    ]
  },
  "order_by": [
    { "field": "date", "direction": "asc" }
  ]
}
```

`viz_config` 示例：

```json
{
  "legend": true,
  "stacked": false,
  "xAxis_label_rotate": 0,
  "show_value_labels": false
}
```

约束：

* `dimensions` 中字段必须是可作为维度的类型（string/date 等）；
* `metrics` 中字段必须是数值型；
* 当 `chart_type = pie` 时：

  * `dimensions` 应为一个字段；
  * `metrics` 仅允许一个指标。

---

### 8.5.3 Table Widget

`query_config` 示例：

```json
{
  "dataset_id": "ds_123",
  "columns": [
    { "field": "date" },
    { "field": "channel" },
    { "field": "amount", "aggregation": "sum", "alias": "total_amount" }
  ],
  "filter": {
    "op": "and",
    "conditions": []
  },
  "order_by": [
    { "field": "date", "direction": "desc" }
  ],
  "limit": 100
}
```

规则：

* 对有 `aggregation` 的列，后端自动生成 group by；
* 没有 aggregation 的列必须是 group by 维度。

---

# 9. 本地 LLM（ollama）集成

## 9.1 场景

* 自动生成表编码（table_code）
* 自动生成字段编码（field_code）

## 9.2 接口约定

### 9.2.1 生成表编码

* 请求：`POST /api/llm/generate_table_code`
* 请求体：

```json
{
  "display_name": "订单表",
  "tenant_id": "t_123"
}
```

* 返回：

```json
{
  "code": "order"
}
```

后端逻辑：

1. 调用本地 ollama，prompt 中包含 display_name；
2. 接收返回文本，做清洗：

   * lower；
   * 非 `[a-z0-9_]` 替换为 `_`；
   * 保证首字符为字母，不是则加前缀如 `t_`；
   * 截断到 50 字符；
3. 若清洗后为空或全部非法，使用本地规则生成（如拼音）；
4. 检查 `(tenant_id, code)` 是否已存在：

   * 已存在则追加 `_1` `_2` 等后缀；
5. 失败时返回 500 且携带 error message，前端提示“自动生成失败，稍后重试”。

### 9.2.2 生成字段编码

* 请求：`POST /api/llm/generate_field_code`
* 请求体：

```json
{
  "display_name": "创建时间",
  "table_code": "order"
}
```

* 返回同上。

缓存与限流（后端实现要求）：

* 对相同 `(display_name, table_code)` 在短时间内重复请求，可复用上次结果；
* 对单租户每分钟生成次数做限制，防止滥用。

## 9.3 前端交互

* 表/字段表单中：

  * 用户输入“表名/字段名”后自动触发一次生成；
  * 显示编码字段为只读；
  * 提供“重新生成”按钮以手动重试；
* 若接口调用失败：

  * 使用 fallback 返回的编码；
  * 若连 fallback 也失败，提示：“编码生成失败，请稍后重试”，并阻止提交。

---

# 10. 非功能要求（简要）

* 多租户隔离：

  * 所有业务表必须包含 `tenant_id` 列；
  * 所有查询/更新都按 `tenant_id` 过滤。
* 权限：

  * 所有需要权限的接口在后端强制检查（资源级 + 行/列级）；
  * 前端基于权限接口隐藏不该显示的按钮。
* 日志：

  * 记录建模变更（表/字段/关系增删改）；
  * Flow 配置变更、运行记录；
  * Board/Dataset/Widget 变更；
  * 权限变更行为。
* 性能：

  * 常规查询场景（10 万～百万级）需保证正常使用体验（可通过分页限制返回行数）；
  * Flow 运行同步返回启动结果，异步处理任务，运行结果通过 Run 记录查看。
