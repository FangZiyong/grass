"""
API 集成测试脚本 - 使用生成的测试数据

用法:
    python test_api.py
"""
import json
import sys

import requests


class APITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.access_token = None
        self.tenant_id = None
        self.session = requests.Session()  # 使用 session 来保持 cookie

    def _print_section(self, title):
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def _print_success(self, message):
        print(f"✓ {message}")

    def _print_error(self, message):
        print(f"✗ {message}")

    def _print_json(self, data):
        print(json.dumps(data, indent=2, ensure_ascii=False))

    def _get_headers(self, include_auth=True, include_tenant=True):
        """生成请求头，包含 Authorization 和可选的 X-Tenant-Id"""
        headers = {}
        if include_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        # 只有在需要且已有 tenant_id 时才添加 X-Tenant-Id
        if include_tenant and self.tenant_id is not None:
            headers["X-Tenant-Id"] = str(self.tenant_id)
        return headers

    def test_login(self, login_name="user1", password="user1user1"):
        """测试用户登录"""
        self._print_section("1. 测试用户登录")
        print(f"登录账号: {login_name} / {password}\n")

        # 登录接口不需要 X-Tenant-Id header
        response = self.session.post(
            f"{self.api_base}/auth/login",
            json={"login_name": login_name, "password": password},
            headers=self._get_headers(include_auth=False, include_tenant=False),
        )

        if response.status_code != 200:
            self._print_error(f"登录失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)

        # 从响应中提取 access_token（在 data.data.access_token）
        response_data = data.get("data", {})
        self.access_token = response_data.get("access_token")
        if not self.access_token:
            self._print_error("未获取到 access_token")
            return False

        # 如果登录响应中包含 tenant 信息，可以直接使用
        tenant_info = response_data.get("tenant")
        if tenant_info and tenant_info.get("tenant_id"):
            self.tenant_id = tenant_info.get("tenant_id")
            print(f"\n提示: 登录响应中包含租户信息，tenant_id = {self.tenant_id}")

        self._print_success("登录成功")
        return True

    def test_get_me(self):
        """获取当前用户信息"""
        self._print_section("2. 获取当前用户信息")

        # /me 接口不需要 X-Tenant-Id header
        response = self.session.get(
            f"{self.api_base}/me",
            headers=self._get_headers(include_tenant=False),
        )

        if response.status_code != 200:
            self._print_error(f"获取用户信息失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取用户信息成功")
        return True

    def test_get_tenants(self):
        """获取租户列表"""
        self._print_section("3. 获取当前用户的租户列表")

        # /tenants 接口不需要 X-Tenant-Id header（用于获取租户列表）
        response = self.session.get(
            f"{self.api_base}/tenants",
            headers=self._get_headers(include_tenant=False),
        )

        if response.status_code != 200:
            self._print_error(f"获取租户列表失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)

        # 从响应中提取 items（在 data.data.items）
        response_data = data.get("data", {})
        items = response_data.get("items", [])
        if not items:
            self._print_error("未找到租户")
            return False

        # 如果还没有设置 tenant_id，使用第一个租户
        if not self.tenant_id:
            self.tenant_id = items[0].get("tenant_id")
            self._print_success(f"获取租户列表成功 (使用租户 ID: {self.tenant_id})")
        else:
            self._print_success(f"获取租户列表成功 (当前租户 ID: {self.tenant_id})")
        return True

    def test_switch_tenant(self):
        """切换租户"""
        if not self.tenant_id:
            self._print_error("未设置 tenant_id，无法切换租户")
            return False

        self._print_section(f"4. 切换到租户 {self.tenant_id}")

        # /tenants/switch 接口不需要 X-Tenant-Id header（用于切换租户）
        # 需要在 POST body 中传递 tenant_id
        response = self.session.post(
            f"{self.api_base}/tenants/switch",
            json={"tenant_id": self.tenant_id},
            headers=self._get_headers(include_tenant=False),
        )

        if response.status_code != 200:
            self._print_error(f"切换租户失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("切换租户成功")
        return True

    def test_get_roles(self):
        """获取角色列表"""
        if not self.tenant_id:
            self._print_error("未设置 tenant_id，无法获取角色列表")
            return False

        self._print_section("5. 获取租户内的角色列表")

        response = self.session.get(
            f"{self.api_base}/roles",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._print_error(f"获取角色列表失败: {response.status_code}")
            try:
                self._print_json(response.json())
            except:
                print(f"响应内容: {response.text[:200]}")
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取角色列表成功")
        return True

    def test_get_role_users(self):
        """获取角色成员列表（通过角色ID）"""
        if not self.tenant_id:
            self._print_error("未设置 tenant_id，无法获取角色成员列表")
            return False

        self._print_section("6. 获取角色成员列表")

        # 先获取角色列表，使用第一个角色
        roles_response = self.session.get(
            f"{self.api_base}/roles",
            headers=self._get_headers(),
        )

        if roles_response.status_code != 200:
            self._print_error("无法获取角色列表，跳过角色成员测试")
            return False

        roles_data = roles_response.json()
        roles_items = roles_data.get("data", {}).get("items", [])
        if not roles_items:
            self._print_error("未找到角色，跳过角色成员测试")
            return False

        role_id = roles_items[0].get("role_id")
        if not role_id:
            self._print_error("角色ID无效，跳过角色成员测试")
            return False

        # 获取该角色的成员列表
        response = self.session.get(
            f"{self.api_base}/roles/{role_id}/users",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._print_error(f"获取角色成员列表失败: {response.status_code}")
            try:
                self._print_json(response.json())
            except:
                print(f"响应内容: {response.text[:200]}")
            return False

        data = response.json()
        self._print_json(data)
        self._print_success(f"获取角色成员列表成功 (角色 ID: {role_id})")
        return True

    def test_get_resource_tree(self):
        """获取资源树"""
        if not self.tenant_id:
            self._print_error("未设置 tenant_id，无法获取资源树")
            return False

        self._print_section("7. 获取资源树 (TABLE scope)")

        # 资源树路径是 /api/resource-trees/{scope}/children
        response = self.session.get(
            f"{self.api_base}/resource-trees/TABLE/children",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._print_error(f"获取资源树失败: {response.status_code}")
            try:
                self._print_json(response.json())
            except:
                print(f"响应内容: {response.text[:200]}")
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取资源树成功")
        return True

    def test_get_role_permissions(self):
        """获取角色权限信息"""
        if not self.tenant_id:
            self._print_error("未设置 tenant_id，无法获取权限信息")
            return False

        self._print_section("8. 获取角色权限信息")

        # 先获取角色列表，使用第一个角色
        roles_response = self.session.get(
            f"{self.api_base}/roles",
            headers=self._get_headers(),
        )

        if roles_response.status_code != 200:
            self._print_error("无法获取角色列表，跳过权限测试")
            return False

        roles_data = roles_response.json()
        roles_items = roles_data.get("data", {}).get("items", [])
        if not roles_items:
            self._print_error("未找到角色，跳过权限测试")
            return False

        role_id = roles_items[0].get("role_id")
        if not role_id:
            self._print_error("角色ID无效，跳过权限测试")
            return False

        # 获取该角色的资源权限
        response = self.session.get(
            f"{self.api_base}/roles/{role_id}/resource-permissions",
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            self._print_error(f"获取权限信息失败: {response.status_code}")
            try:
                self._print_json(response.json())
            except:
                print(f"响应内容: {response.text[:200]}")
            return False

        data = response.json()
        self._print_json(data)
        self._print_success(f"获取权限信息成功 (角色 ID: {role_id})")
        return True

    def test_logout(self):
        """测试登出"""
        self._print_section("9. 用户登出")

        # 登出接口不需要 X-Tenant-Id header
        # 登出需要 refresh token cookie（由 session 自动处理）
        response = self.session.post(
            f"{self.api_base}/auth/logout",
            headers=self._get_headers(include_tenant=False),
        )

        if response.status_code != 200:
            self._print_error(f"登出失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("登出成功")
        return True

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("  API 集成测试 - 使用测试数据")
        print("=" * 60)

        tests = [
            self.test_login,
            self.test_get_me,
            self.test_get_tenants,
            self.test_switch_tenant,
            self.test_get_roles,
            self.test_get_role_users,
            self.test_get_resource_tree,
            self.test_get_role_permissions,
            self.test_logout,
        ]

        success_count = 0
        total_count = len(tests)

        for test in tests:
            try:
                if test():
                    success_count += 1
                else:
                    print(f"\n⚠️  测试 {test.__name__} 失败")
            except Exception as e:
                print(f"\n❌ 测试 {test.__name__} 异常: {e}")

        # 最终结果
        print("\n" + "=" * 60)
        print(f"  测试结果: {success_count}/{total_count} 成功")
        print("=" * 60)

        return success_count == total_count


def main():
    """主函数"""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

    tester = APITester(base_url)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
