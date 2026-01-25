# 快速开始 - 测试数据

## 一键生成测试数据

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 进入项目目录
cd src

# 3. 生成测试数据
python manage.py seed_data

# 或者自定义数量
python manage.py seed_data --users 20 --tenants 5

# 清空现有数据后重新生成
python manage.py seed_data --clear
```

## 测试账号

生成完成后，可以使用以下账号登录系统：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| user1 | user1user1 | 平台管理员 | 拥有平台管理权限 |
| user2 | user2user2 | 普通用户 | - |
| user3 | user3user3 | 普通用户 | - |
| ... | ... | ... | 以此类推 |

## 生成的数据概览

### 默认配置（10 用户 + 3 租户）

```
全局用户 (10个)
  ├── user1 (平台管理员) - user1user1
  ├── user2 - user2user2
  ├── user3 - user3user3
  └── ...

租户 (3个)
  ├── TENANT_1000 (租户1) - BASIC 套餐
  │   ├── 成员 (5人): user1~user5
  │   ├── 角色 (4个): 管理员、开发者、分析师、访客
  │   ├── 资源树 (52个节点): TABLE/FLOW/DATASET/DASHBOARD
  │   └── 权限 (48条): 角色级权限配置
  │
  ├── TENANT_1001 (租户2) - PRO 套餐
  │   └── ... (结构相同)
  │
  └── TENANT_1002 (租户3) - ENTERPRISE 套餐
      └── ... (结构相同)
```

### 角色说明

每个租户包含 4 个内置角色：

1. **管理员 (admin)**
   - 权限：所有资源的 MANAGE 权限
   - 成员：租户 Owner

2. **开发者 (developer)**
   - 权限：FLOW、DATASET 的 EDIT 权限
   - 成员：部分租户成员

3. **分析师 (analyst)**
   - 权限：所有资源的 VIEW 权限
   - 成员：部分租户成员

4. **访客 (viewer)**
   - 权限：测试环境文件夹的 VIEW 权限
   - 成员：部分租户成员

### 资源树结构

每个租户的每个资源域（TABLE/FLOW/DATASET/DASHBOARD）都包含：

```
ROOT/
├── 生产环境/
│   ├── 资源1
│   ├── 资源2
│   └── 资源3
├── 测试环境/
│   ├── 资源1
│   ├── 资源2
│   └── 资源3
└── 开发环境/
    ├── 资源1
    ├── 资源2
    └── 资源3
```

## 验证数据

```bash
# 查看数据统计
python manage.py shell -c "
from apps.accounts.models.users import GlobalUser
from apps.tenants.models.tenant import Tenant
from apps.iam.models.roles import Role
from apps.resource_tree.models.resource_node import ResourceTreeNode

print(f'用户数: {GlobalUser.objects.count()}')
print(f'租户数: {Tenant.objects.count()}')
print(f'角色数: {Role.objects.count()}')
print(f'资源树节点数: {ResourceTreeNode.objects.count()}')
"

# 测试登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login_name": "user1", "password": "user1user1"}'
```

## 常见场景

### 场景 1: 测试用户登录

```bash
# 使用 user1 (平台管理员) 登录
login_name: user1
password: user1user1

# 使用 user2 (普通用户) 登录
login_name: user2
password: user2user2
```

### 场景 2: 测试租户切换

user1 是前 3 个租户的成员，登录后可以切换到不同租户：
- TENANT_1000 (租户1)
- TENANT_1001 (租户2)
- TENANT_1002 (租户3)

### 场景 3: 测试权限控制

- **管理员**: 可以管理租户内所有资源
- **开发者**: 可以编辑流程和数据集
- **分析师**: 可以查看所有资源
- **访客**: 只能查看测试环境的数据集

### 场景 4: 测试资源树操作

每个租户都有完整的资源树结构，可以测试：
- 文件夹创建/重命名/删除
- 资源添加/移动/删除
- 层级关系管理

## 清理数据

如果需要清空测试数据：

```bash
# 方式 1: 使用脚本清空并重新生成
python manage.py seed_data --clear

# 方式 2: 手动删除（Django shell）
python manage.py shell -c "
from apps.iam.models.grants import RolePermission
from apps.iam.models.membership import TenantUserRole
from apps.resource_tree.models.resource_node import ResourceTreeNode
from apps.iam.models.roles import Role
from apps.tenants.models.tenant_user import TenantUser
from apps.tenants.models.tenant import Tenant
from apps.accounts.models.users import GlobalUser

RolePermission.objects.all().delete()
TenantUserRole.objects.all().delete()
ResourceTreeNode.objects.all().delete()
Role.objects.all().delete()
TenantUser.objects.all().delete()
Tenant.objects.all().delete()
GlobalUser.objects.all().delete()

print('数据已清空')
"
```

## 自定义数据

如需自定义生成逻辑，可以编辑脚本：

```
src/apps/accounts/management/commands/seed_data.py
```

可自定义的内容：
- 用户名规则
- 密码规则
- 租户名称
- 角色配置
- 资源树结构
- 权限分配规则

## 下一步

1. 启动开发服务器：`python manage.py runserver`
2. 使用 user1/user1user1 登录
3. 测试各项功能

详细文档请参考：[docs/seed_data.md](./seed_data.md)
