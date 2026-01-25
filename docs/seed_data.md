# 测试数据生成脚本

## 概述

`seed_data` 命令用于快速生成测试数据，包括用户、租户、角色、资源树和权限等。

## 使用方法

### 基本用法

```bash
# 激活虚拟环境
source .venv/bin/activate

# 生成默认数据（10个用户，3个租户）
cd src
python manage.py seed_data

# 自定义数量
python manage.py seed_data --users 20 --tenants 5

# 清空现有数据后再生成
python manage.py seed_data --clear
```

### 参数说明

- `--users <数量>`: 创建的用户数量，默认 10
- `--tenants <数量>`: 创建的租户数量，默认 3
- `--clear`: 清空现有数据后再生成（慎用！）

## 生成的数据

### 1. 全局用户 (GlobalUser)

- **用户名格式**: `user1`, `user2`, `user3`, ...
- **密码格式**: `user1user1`, `user2user2`, `user3user3`, ...
- **邮箱格式**: `user1@example.com`, `user2@example.com`, ...
- **显示名**: 用户1, 用户2, 用户3, ...
- **特殊说明**: `user1` 是平台管理员

### 2. 租户 (Tenant)

- **租户名**: 租户1, 租户2, 租户3, ...
- **租户代码**: 自动生成 (TENANT_1000, TENANT_1001, ...)
- **套餐计划**: 循环分配 BASIC, PRO, ENTERPRISE
- **状态**: 全部为 ACTIVE

### 3. 租户成员 (TenantUser)

- 每个租户添加前 5 个用户（或所有用户，取较小值）
- 第一个用户为租户 Owner
- 其他成员状态为 ACTIVE

### 4. 角色 (Role)

每个租户创建 4 个内置角色：

| 角色代码 | 角色名称 | 说明 |
|---------|---------|------|
| admin | 管理员 | 租户管理员，拥有所有权限 |
| developer | 开发者 | 可以创建和编辑流程、数据集等 |
| analyst | 分析师 | 可以查看数据和报表 |
| viewer | 访客 | 只能查看授权的资源 |

### 5. 成员角色分配 (TenantUserRole)

- Owner → 管理员角色
- 其他成员按顺序轮流分配：开发者、分析师、访客

### 6. 资源树 (ResourceTreeNode)

为每个租户的每个资源域（TABLE、FLOW、DATASET、DASHBOARD）创建：

```
ROOT/
├── 生产环境/
│   ├── 用户表1 (或对应资源)
│   ├── 用户表2
│   └── 用户表3
├── 测试环境/
│   ├── 用户表1
│   ├── 用户表2
│   └── 用户表3
└── 开发环境/
    ├── 用户表1
    ├── 用户表2
    └── 用户表3
```

每个租户共创建约 52 个节点（4 个根节点 + 12 个文件夹 + 36 个资源）

### 7. 权限配置 (RolePermission)

| 角色 | 权限配置 |
|------|---------|
| 管理员 | 所有资源域的根节点 → MANAGE |
| 开发者 | FLOW、DATASET 根节点 → EDIT |
| 分析师 | 所有资源域的根节点 → VIEW |
| 访客 | 包含"测试"的文件夹 → VIEW (仅 DATASET) |

## 示例登录账号

生成完成后，可以使用以下账号登录：

```
用户名: user1    密码: user1user1   (平台管理员)
用户名: user2    密码: user2user2
用户名: user3    密码: user3user3
...
```

## 数据统计

以默认参数（10 个用户，3 个租户）为例：

- 全局用户: 10 个
- 租户: 3 个
- 租户成员关系: 15 个 (每个租户 5 个成员)
- 角色: 12 个 (每个租户 4 个角色)
- 成员角色分配: 15 个
- 资源树节点: 156 个 (每个租户 52 个)
- 权限记录: 根据角色和资源树自动配置

## 注意事项

1. **幂等性**: 脚本使用 `get_or_create`，重复运行不会创建重复数据
2. **清空数据**: 使用 `--clear` 参数会删除所有相关数据，请谨慎使用
3. **事务保护**: 所有数据生成在一个事务中完成，失败会自动回滚
4. **密码加密**: 密码使用 Django 的 `make_password` 进行哈希加密

## 验证数据

生成后可以通过以下方式验证：

```bash
# 查看用户数量
python manage.py shell -c "from apps.accounts.models.users import GlobalUser; print(GlobalUser.objects.count())"

# 查看租户数量
python manage.py shell -c "from apps.tenants.models.tenant import Tenant; print(Tenant.objects.count())"

# 查看某个租户的资源树
python manage.py shell -c "from apps.resource_tree.models.resource_node import ResourceTreeNode; print(ResourceTreeNode.objects.filter(tenant_id=1).count())"
```

## 故障排除

### 问题：命令找不到

确保 Django app 已在 `INSTALLED_APPS` 中注册：

```python
INSTALLED_APPS = [
    ...
    'apps.accounts',
    ...
]
```

### 问题：外键约束错误

确保数据库迁移已应用：

```bash
python manage.py migrate
```

### 问题：重复键冲突

如果不想清空数据，可以手动调整脚本中的用户名、邮箱等唯一字段的生成逻辑。
