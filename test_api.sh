#!/bin/bash
# API 测试脚本 - 使用生成的测试数据
# 用法：./test_api.sh

BASE_URL="http://localhost:8000"
API_BASE="$BASE_URL/api/v1"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "API 测试脚本 - 使用测试数据"
echo "=================================================="
echo ""

# 1. 用户登录
echo -e "${YELLOW}1. 测试用户登录${NC}"
echo "登录账号: user1 / user1user1"
echo ""

LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "login_name": "user1",
    "password": "user1user1"
  }')

echo "$LOGIN_RESPONSE" | python3 -m json.tool

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ]; then
    echo -e "${RED}✗ 登录失败${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 登录成功${NC}"
echo ""

# 2. 获取当前用户信息
echo -e "${YELLOW}2. 获取当前用户信息${NC}"
echo ""

ME_RESPONSE=$(curl -s -X GET "$API_BASE/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$ME_RESPONSE" | python3 -m json.tool

echo -e "${GREEN}✓ 获取用户信息成功${NC}"
echo ""

# 3. 获取租户列表
echo -e "${YELLOW}3. 获取当前用户的租户列表${NC}"
echo ""

TENANTS_RESPONSE=$(curl -s -X GET "$API_BASE/tenants" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$TENANTS_RESPONSE" | python3 -m json.tool

TENANT_ID=$(echo "$TENANTS_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('items', [{}])[0].get('tenant_id', '') if 'items' in data else '')" 2>/dev/null)

if [ -z "$TENANT_ID" ]; then
    echo -e "${RED}✗ 未找到租户${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 获取租户列表成功 (使用租户 ID: $TENANT_ID)${NC}"
echo ""

# 4. 切换租户上下文
echo -e "${YELLOW}4. 切换到租户 $TENANT_ID${NC}"
echo ""

SWITCH_RESPONSE=$(curl -s -X POST "$API_BASE/tenants/$TENANT_ID/switch" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$SWITCH_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 切换租户成功${NC}"
echo ""

# 5. 获取当前租户的角色列表
echo -e "${YELLOW}5. 获取租户内的角色列表${NC}"
echo ""

ROLES_RESPONSE=$(curl -s -X GET "$API_BASE/iam/roles" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Tenant-Id: $TENANT_ID")

echo "$ROLES_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 获取角色列表成功${NC}"
echo ""

# 6. 获取租户成员列表
echo -e "${YELLOW}6. 获取租户成员列表${NC}"
echo ""

MEMBERS_RESPONSE=$(curl -s -X GET "$API_BASE/iam/members" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Tenant-Id: $TENANT_ID")

echo "$MEMBERS_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 获取成员列表成功${NC}"
echo ""

# 7. 获取资源树
echo -e "${YELLOW}7. 获取资源树 (TABLE scope)${NC}"
echo ""

TREE_RESPONSE=$(curl -s -X GET "$API_BASE/resource-tree?scope=TABLE" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Tenant-Id: $TENANT_ID")

echo "$TREE_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 获取资源树成功${NC}"
echo ""

# 8. 获取当前用户的权限
echo -e "${YELLOW}8. 获取当前用户的权限信息${NC}"
echo ""

PERMISSIONS_RESPONSE=$(curl -s -X GET "$API_BASE/iam/permissions/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Tenant-Id: $TENANT_ID")

echo "$PERMISSIONS_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 获取权限信息成功${NC}"
echo ""

# 9. 刷新 Token
echo -e "${YELLOW}9. 刷新访问令牌${NC}"
echo ""

REFRESH_RESPONSE=$(curl -s -X POST "$API_BASE/auth/refresh" \
  -H "Content-Type: application/json" \
  -b "refresh_token=xxx")  # 注意：需要从 cookie 中获取

echo "$REFRESH_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ Token 刷新测试完成（需要有效的 refresh cookie）${NC}"
echo ""

# 10. 登出
echo -e "${YELLOW}10. 用户登出${NC}"
echo ""

LOGOUT_RESPONSE=$(curl -s -X POST "$API_BASE/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$LOGOUT_RESPONSE" | python3 -m json.tool
echo -e "${GREEN}✓ 登出成功${NC}"
echo ""

echo "=================================================="
echo -e "${GREEN}所有测试完成！${NC}"
echo "=================================================="
