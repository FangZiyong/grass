# T0.4 认证上下文测试说明

## 测试文件位置

`src/apps/accounts/tests/test_auth_context.py`

## 测试覆盖

### ✅ 任务要求的 5 个核心分支

1. **无 token（允许匿名访问）**
   - `test_authenticate_no_token` - 认证类允许无 token
   - `test_public_view_no_token` - 公开视图允许匿名访问
   - `test_protected_view_no_token` - 受保护视图无 token 返回 401

2. **token 过期**
   - `test_verify_access_token_expired` - Token 工具函数验证过期 token
   - `test_authenticate_expired_token` - 认证类处理过期 token
   - `test_protected_view_expired_token` - API 视图处理过期 token

3. **签名错误/无效 token**
   - `test_verify_access_token_invalid_signature` - 签名错误
   - `test_verify_access_token_missing_user_id` - 缺少必需字段
   - `test_verify_access_token_wrong_type` - 错误 token 类型
   - `test_authenticate_invalid_signature` - 认证类处理签名错误
   - `test_protected_view_invalid_signature` - API 视图处理签名错误
   - `test_protected_view_malformed_header` - 格式错误的 header

4. **正常认证（普通用户）**
   - `test_issue_access_token` - 签发普通用户 token
   - `test_verify_access_token_valid` - 验证有效 token
   - `test_authenticate_valid_token` - 认证类处理有效 token
   - `test_protected_view_valid_token` - API 视图正常访问

5. **正常认证（平台管理员）**
   - `test_issue_access_token_platform_admin` - 签发平台管理员 token
   - `test_authenticate_platform_admin_token` - 认证类处理平台管理员 token
   - `test_admin_view_platform_admin` - 管理员视图正常访问

### 额外测试覆盖

- **Token 工具函数测试**（8 个测试）
  - Header 提取（有效/无效格式）
  - Token 签发（普通用户/平台管理员）
  - Token 验证（有效/过期/签名错误/缺少字段/错误类型）

- **JWT 认证类测试**（7 个测试）
  - 无 token、有效 token、平台管理员 token
  - 过期 token、签名错误、格式错误 header
  - authenticate_header 方法

- **AuthContextUser 测试**（3 个测试）
  - 用户创建、平台管理员标识、字符串表示

- **端到端 API 测试**（9 个测试）
  - 公开视图、受保护视图、管理员视图
  - 各种 token 场景（有效/过期/签名错误/格式错误）
  - 权限检查（普通用户访问管理员视图）
  - Request ID 传递

## 运行测试

```bash
# 运行所有认证上下文测试
python src/manage.py test apps.accounts.tests.test_auth_context

# 运行特定测试类
python src/manage.py test apps.accounts.tests.test_auth_context.TokenUtilsTests
python src/manage.py test apps.accounts.tests.test_auth_context.JWTAuthenticationTests
python src/manage.py test apps.accounts.tests.test_auth_context.AuthContextAPITests

# 详细输出
python src/manage.py test apps.accounts.tests.test_auth_context --verbosity=2
```

## 测试统计

- **总测试数**: 28 个
- **测试类**: 5 个
  - `TokenUtilsTests` - 8 个测试
  - `JWTAuthenticationTests` - 7 个测试
  - `AuthContextUserTests` - 3 个测试
  - `AuthContextAPITests` - 9 个测试
  - `AuthContextAPITests` (端到端) - 1 个额外测试

## 验收标准检查

- ✅ **单测覆盖**：至少 5 个分支（无 token；token 过期；签名错；正常；平台管理员）
- ✅ **符合统一返回壳与错误码**：所有 API 测试使用 `envelope_response`，错误码符合规范
- ✅ **符合 TenantContext / 权限 / 审计 / 分页约束**：为后续权限判断提供 `user_id`、`is_platform_admin` 字段
- ✅ **migrations 可运行**：本任务不涉及模型变更
