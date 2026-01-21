# T0.4 认证上下文测试说明

## 测试覆盖

测试文件：`test_auth_context.py`

### Token 工具函数测试（TokenUtilsTests）
1. ✅ 从有效的 Authorization header 中提取 token
2. ✅ 无效格式的 header 处理
3. ✅ 签发 access token（普通用户）
4. ✅ 签发 access token（平台管理员）
5. ✅ 验证有效的 token
6. ✅ 验证过期的 token
7. ✅ 验证签名错误的 token
8. ✅ 验证缺少 user_id 的 token
9. ✅ 验证错误类型的 token

### JWT 认证类测试（JWTAuthenticationTests）
1. ✅ 无 token 的情况（允许匿名访问）
2. ✅ 有效的 token（普通用户）
3. ✅ 有效的 token（平台管理员）
4. ✅ 过期的 token
5. ✅ 签名错误的 token
6. ✅ 格式错误的 Authorization header
7. ✅ authenticate_header 方法

### AuthContextUser 测试（AuthContextUserTests）
1. ✅ 创建 AuthContextUser
2. ✅ 平台管理员用户
3. ✅ 字符串表示

## 运行测试

```bash
# 使用 Django 测试框架
python src/manage.py test apps.accounts.tests.test_auth_context

# 或使用 pytest
pytest src/apps/accounts/tests/test_auth_context.py -v
```

## 验收标准检查

- ✅ 单测覆盖：至少 5 个分支（无 token；token 过期；签名错；正常；平台管理员）
- ✅ 符合统一返回壳与错误码（tech.md §3.3）
- ✅ 符合 TenantContext / 权限 / 审计 / 分页约束（tech.md §3.9）
- ✅ migrations 可运行（本任务不涉及模型变更）

