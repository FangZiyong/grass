# Grass - 多租户数据管理平台

## 快速开始

### 1. 安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制环境变量文件
cp .env.dev .env

# 编辑数据库配置等
vim .env
```

### 3. 数据库迁移

```bash
cd src
python manage.py migrate
```

### 4. 生成测试数据

```bash
# 生成默认测试数据（10个用户，3个租户）
python manage.py seed_data

# 或自定义数量
python manage.py seed_data --users 20 --tenants 5
```

生成的测试账号：
- 用户名：`user1`, `user2`, ...
- 密码：`user1user1`, `user2user2`, ...
- `user1` 是平台管理员

详细文档：[docs/QUICKSTART_DATA.md](docs/QUICKSTART_DATA.md)

### 5. 启动服务

```bash
# 开发服务器
python manage.py runserver

# 或指定端口
python manage.py runserver 0.0.0.0:8000
```

### 6. 测试 API

```bash
# 方式 1: 使用 curl
./test_api.sh

# 方式 2: 使用 Python 脚本
python test_api.py
```

## 项目结构

```
grass/
├── src/                        # 源代码目录
│   ├── apps/                   # Django 应用
│   │   ├── accounts/           # 用户认证与账号管理
│   │   ├── tenants/            # 租户管理
│   │   ├── iam/                # 身份与访问管理（角色、权限）
│   │   ├── resource_tree/      # 资源树管理
│   │   └── execution/          # 任务执行引擎
│   ├── common/                 # 公共模块
│   │   ├── errors/             # 错误处理
│   │   ├── http/               # HTTP 工具
│   │   └── middleware/         # 中间件
│   ├── config/                 # 配置
│   │   ├── settings/           # 环境配置
│   │   └── urls.py             # 路由配置
│   └── integrations/           # 第三方集成
│       └── storage/            # 存储客户端
├── docs/                       # 文档
│   ├── architecture.md         # 架构设计
│   ├── tech.md                 # 技术方案
│   ├── prd.md                  # 产品需求
│   ├── task.md                 # 任务列表
│   ├── seed_data.md            # 测试数据详细说明
│   ├── seed_data_implementation.md  # 脚本实现说明
│   └── QUICKSTART_DATA.md      # 快速开始 - 测试数据
├── test_api.sh                 # API 测试脚本（bash）
├── test_api.py                 # API 测试脚本（Python）
└── requirements.txt            # Python 依赖
```

## 核心功能

### 1. 多租户架构

- **租户隔离**：数据、权限、配置完全隔离
- **租户套餐**：BASIC / PRO / ENTERPRISE
- **租户状态管理**：ACTIVE / SUSPENDED

### 2. 身份与访问管理 (IAM)

- **用户管理**：平台用户、租户成员
- **角色管理**：自定义角色、内置角色
- **权限控制**：资源级权限、行列级权限
- **成员管理**：租户成员、角色分配

### 3. 资源树管理

- **层级结构**：文件夹、资源节点
- **多资源域**：TABLE / FLOW / DATASET / DASHBOARD
- **路径继承**：权限继承、批量操作
- **软删除**：安全删除、可恢复

### 4. 认证与授权

- **登录认证**：用户名密码登录
- **Token 管理**：Access Token + Refresh Token
- **会话管理**：设备信息、主动撤销
- **限流保护**：登录限流、防暴力破解

### 5. 任务执行引擎

- **任务调度**：Celery 异步任务
- **任务日志**：执行记录、状态追踪
- **任务重试**：失败重试、错误处理

## API 文档

API 文档位于 `docs/api/` 目录：

- OpenAPI 规范：`docs/api/openapi.yaml`
- 接口定义：`docs/api/paths/`
- 在线文档：启动服务后访问 `/api/docs/`

主要 API 端点：

- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `POST /api/v1/auth/refresh` - 刷新 Token
- `GET /api/v1/me` - 获取当前用户信息
- `GET /api/v1/tenants` - 获取租户列表
- `POST /api/v1/tenants/{id}/switch` - 切换租户
- `GET /api/v1/iam/roles` - 获取角色列表
- `GET /api/v1/iam/members` - 获取成员列表
- `GET /api/v1/iam/permissions/me` - 获取当前用户权限
- `GET /api/v1/resource-tree` - 获取资源树

## 开发指南

### 代码规范

- 遵循 PEP 8 代码风格
- 使用类型注解
- 编写文档字符串
- 保持函数简洁

详见：`docs/conventions.md`

### 测试

```bash
# 运行所有测试
pytest

# 运行特定应用的测试
pytest src/apps/accounts/tests/

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 数据库迁移

```bash
# 创建迁移文件
python manage.py makemigrations

# 应用迁移
python manage.py migrate

# 查看迁移状态
python manage.py showmigrations
```

### 生成测试数据

```bash
# 生成默认数据
python manage.py seed_data

# 自定义数量
python manage.py seed_data --users 20 --tenants 5

# 清空并重新生成
python manage.py seed_data --clear
```

详见：`docs/seed_data.md`

## 环境变量

主要环境变量：

```bash
# Django 配置
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# 数据库配置
DB_NAME=grass
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# 认证配置
AUTH_ACCESS_TOKEN_TTL_SECONDS=3600
AUTH_REFRESH_TOKEN_TTL_DAYS=30
AUTH_REQUIRE_TLS=False

# Celery 配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## 部署

### 生产环境配置

```bash
# 使用生产环境配置
export DJANGO_SETTINGS_MODULE=config.settings.prod

# 收集静态文件
python manage.py collectstatic --noinput

# 使用 gunicorn 启动
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

### Docker 部署

```bash
# 构建镜像
docker build -t grass:latest .

# 运行容器
docker run -d -p 8000:8000 grass:latest
```

## 文档

- [架构设计](docs/architecture.md)
- [技术方案](docs/tech.md)
- [产品需求](docs/prd.md)
- [测试数据说明](docs/seed_data.md)
- [快速开始 - 测试数据](docs/QUICKSTART_DATA.md)
- [脚本实现说明](docs/seed_data_implementation.md)

## 许可证

[MIT License](LICENSE)

## 联系方式

- Issue: [GitHub Issues](https://github.com/yourusername/grass/issues)
- Email: your.email@example.com
