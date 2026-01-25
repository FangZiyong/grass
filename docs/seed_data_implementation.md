# 数据生成脚本说明

## 脚本位置

```
src/apps/accounts/management/commands/seed_data.py
```

## 核心功能

该脚本实现了完整的测试数据生成功能，遵循系统的业务逻辑和数据模型关系。

## 数据生成流程

### 1. 创建全局用户 (GlobalUser)

```python
def _create_users(self, num_users):
    # 用户名: user1, user2, ...
    # 密码: user1user1, user2user2, ...
    # user1 设置为平台管理员
```

**关键字段**:
- `login_name`: 全局唯一，不可修改
- `password_hash`: 使用 Django 的 `make_password()` 加密
- `email`: 全局唯一
- `is_platform_admin`: user1 为 True
- `status`: 默认 ACTIVE

### 2. 创建租户 (Tenant)

```python
def _create_tenants(self, num_tenants):
    # 租户名: 租户1, 租户2, ...
    # 套餐: 循环分配 BASIC/PRO/ENTERPRISE
```

**关键字段**:
- `code`: 自动生成（TENANT_1000 起）
- `name`: 租户1, 租户2, ...
- `plan`: BASIC/PRO/ENTERPRISE 循环分配
- `status`: 默认 ACTIVE

### 3. 创建租户成员 (TenantUser)

```python
def _create_tenant_users(self, tenant, users):
    # 每个租户添加前 5 个用户
    # 第一个用户设为 Owner
```

**关键逻辑**:
- 每个租户添加前 min(5, len(users)) 个用户
- 第一个用户 `is_owner=True`
- 其他成员 `status=ACTIVE`

### 4. 创建角色 (Role)

```python
def _create_roles(self, tenant, tenant_users):
    # 创建 4 个内置角色
    role_configs = [
        {"code": "admin", "name": "管理员", ...},
        {"code": "developer", "name": "开发者", ...},
        {"code": "analyst", "name": "分析师", ...},
        {"code": "viewer", "name": "访客", ...},
    ]
```

**角色配置**:
| 角色代码 | 角色名称 | 描述 | 内置 |
|---------|---------|------|------|
| admin | 管理员 | 租户管理员，拥有所有权限 | ✓ |
| developer | 开发者 | 可以创建和编辑流程、数据集等 | ✓ |
| analyst | 分析师 | 可以查看数据和报表 | ✓ |
| viewer | 访客 | 只能查看授权的资源 | ✓ |

### 5. 分配角色 (TenantUserRole)

```python
def _assign_roles(self, tenant, tenant_users, roles):
    # Owner → 管理员
    # 其他成员按序分配：developer, analyst, viewer
```

**分配规则**:
- Owner (第一个用户) → admin 角色
- 其他成员按索引模 3 分配：
  - i % 3 == 1 → developer
  - i % 3 == 2 → analyst
  - i % 3 == 0 → viewer

### 6. 创建资源树 (ResourceTreeNode)

```python
def _create_resource_tree(self, tenant, owner):
    # 1. 确保根节点存在（每个 scope 一个）
    # 2. 为每个 scope 创建 3 个文件夹
    # 3. 每个文件夹下创建 3 个资源
```

**资源树结构**:
```
每个 scope (TABLE/FLOW/DATASET/DASHBOARD):
  ROOT/
  ├── 生产环境/
  │   ├── 资源1 (ref_resource_id: 1001)
  │   ├── 资源2 (ref_resource_id: 1002)
  │   └── 资源3 (ref_resource_id: 1003)
  ├── 测试环境/
  │   ├── 资源1 (ref_resource_id: 1001)
  │   ├── 资源2 (ref_resource_id: 1002)
  │   └── 资源3 (ref_resource_id: 1003)
  └── 开发环境/
      ├── 资源1 (ref_resource_id: 1001)
      ├── 资源2 (ref_resource_id: 1002)
      └── 资源3 (ref_resource_id: 1003)
```

**节点统计**:
- 4 个 scope × (1 个根 + 3 个文件夹 + 9 个资源) = 52 个节点/租户

### 7. 配置权限 (RolePermission)

```python
def _assign_permissions(self, tenant, roles, nodes, owner):
    # 为不同角色配置不同的权限级别
```

**权限配置矩阵**:

| 角色 | 资源范围 | 权限级别 | 说明 |
|------|---------|---------|------|
| admin | 所有 scope 的根节点 | MANAGE | 对所有资源类型都有管理权限 |
| developer | FLOW、DATASET 根节点 | EDIT | 可编辑流程和数据集 |
| analyst | 所有 scope 的根节点 | VIEW | 可查看所有资源 |
| viewer | 包含"测试"的文件夹 | VIEW | 仅可查看测试环境的数据集 |

**权限继承**:
- 资源树采用路径继承策略
- 父节点的权限会传递给子节点
- 例如：根节点的 VIEW 权限会覆盖所有子资源

## 事务保护

所有数据生成在一个事务中完成：

```python
with transaction.atomic():
    if clear_data:
        self._clear_existing_data()
    
    users = self._create_users(num_users)
    tenants = self._create_tenants(num_tenants)
    # ... 其他操作
```

**好处**:
- 全部成功或全部回滚
- 保证数据一致性
- 避免生成部分数据

## 幂等性设计

使用 `get_or_create()` 确保重复运行不会创建重复数据：

```python
user, created = GlobalUser.objects.get_or_create(
    login_name=login_name,
    defaults={...}
)

if not created:
    # 如果用户已存在，更新密码
    user.password_hash = make_password(password)
    user.save(update_fields=["password_hash"])
```

## 依赖关系处理

严格按照外键依赖顺序创建数据：

```
1. GlobalUser (无依赖)
2. Tenant (无依赖)
3. TenantUser (依赖 Tenant, GlobalUser)
4. Role (依赖 Tenant, TenantUser)
5. TenantUserRole (依赖 Tenant, TenantUser, Role)
6. ResourceTreeNode (依赖 Tenant, TenantUser)
7. RolePermission (依赖 Tenant, Role, ResourceTreeNode, TenantUser)
```

## 数据量估算

默认配置（10 用户 + 3 租户）:

```
GlobalUser:        10 条
Tenant:            3 条
TenantUser:        15 条 (3 租户 × 5 成员)
Role:              12 条 (3 租户 × 4 角色)
TenantUserRole:    15 条 (每个成员 1 个角色)
ResourceTreeNode:  156 条 (3 租户 × 52 节点)
RolePermission:    ~144 条 (3 租户 × 48 权限)
---
总计:              ~355 条记录
```

## 性能优化

1. **批量查询**: 使用 `select_related()` 和 `prefetch_related()`
2. **事务批处理**: 单个事务完成所有写入
3. **索引利用**: 依赖数据库索引加速查询
4. **幂等操作**: 使用 `get_or_create()` 避免冲突

## 扩展性

如需自定义，可以修改以下方法：

```python
# 自定义用户生成逻辑
def _create_users(self, num_users):
    pass

# 自定义租户生成逻辑
def _create_tenants(self, num_tenants):
    pass

# 自定义角色配置
def _create_roles(self, tenant, tenant_users):
    pass

# 自定义资源树结构
def _create_resource_tree(self, tenant, owner):
    pass

# 自定义权限配置
def _assign_permissions(self, tenant, roles, nodes, owner):
    pass
```

## 注意事项

1. **密码安全**: 测试数据的密码简单，生产环境必须使用强密码
2. **数据清理**: `--clear` 参数会删除所有数据，谨慎使用
3. **并发安全**: 租户 code 生成使用唯一约束 + 重试机制
4. **外键保护**: 使用 `PROTECT` 防止误删关键关联数据
5. **软删除**: ResourceTreeNode 使用 `is_deleted` 标记

## 测试建议

生成数据后，建议测试以下场景：

1. ✓ 用户登录（验证密码正确）
2. ✓ 租户切换（验证成员关系）
3. ✓ 角色权限（验证权限控制）
4. ✓ 资源树操作（验证层级关系）
5. ✓ 权限继承（验证路径继承）
6. ✓ 并发访问（验证事务隔离）

## 问题排查

### 问题 1: 命令找不到

**原因**: Django app 未注册

**解决**: 确保 `apps.accounts` 在 `INSTALLED_APPS` 中

### 问题 2: 外键约束错误

**原因**: 数据库迁移未应用

**解决**: `python manage.py migrate`

### 问题 3: 重复键冲突

**原因**: 唯一约束冲突

**解决**: 使用 `--clear` 清空后重新生成

### 问题 4: 性能慢

**原因**: 数据量大或数据库性能问题

**优化**: 
- 减少生成数量
- 检查数据库索引
- 使用 SSD 存储

## 相关文件

- 脚本文件: `src/apps/accounts/management/commands/seed_data.py`
- 详细文档: `docs/seed_data.md`
- 快速开始: `docs/QUICKSTART_DATA.md`
- 模型定义: 
  - `src/apps/accounts/models/users.py`
  - `src/apps/tenants/models/tenant.py`
  - `src/apps/iam/models/roles.py`
  - `src/apps/resource_tree/models/resource_node.py`
