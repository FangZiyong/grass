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
        self.api_base = f"{base_url}/api/v1"
        self.access_token = None
        self.tenant_id = None

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

    def test_login(self, login_name="user1", password="user1user1"):
        """测试用户登录"""
        self._print_section("1. 测试用户登录")
        print(f"登录账号: {login_name} / {password}\n")

        response = requests.post(
            f"{self.api_base}/auth/login",
            json={"login_name": login_name, "password": password},
        )

        if response.status_code != 200:
            self._print_error(f"登录失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)

        self.access_token = data.get("access_token")
        if not self.access_token:
            self._print_error("未获取到 access_token")
            return False

        self._print_success("登录成功")
        return True

    def test_get_me(self):
        """获取当前用户信息"""
        self._print_section("2. 获取当前用户信息")

        response = requests.get(
            f"{self.api_base}/me",
            headers={"Authorization": f"Bearer {self.access_token}"},
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

        response = requests.get(
            f"{self.api_base}/tenants",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

        if response.status_code != 200:
            self._print_error(f"获取租户列表失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)

        items = data.get("items", [])
        if not items:
            self._print_error("未找到租户")
            return False

        self.tenant_id = items[0].get("tenant_id")
        self._print_success(f"获取租户列表成功 (使用租户 ID: {self.tenant_id})")
        return True

    def test_switch_tenant(self):
        """切换租户"""
        self._print_section(f"4. 切换到租户 {self.tenant_id}")

        response = requests.post(
            f"{self.api_base}/tenants/{self.tenant_id}/switch",
            headers={"Authorization": f"Bearer {self.access_token}"},
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
        self._print_section("5. 获取租户内的角色列表")

        response = requests.get(
            f"{self.api_base}/iam/roles",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-Id": str(self.tenant_id),
            },
        )

        if response.status_code != 200:
            self._print_error(f"获取角色列表失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取角色列表成功")
        return True

    def test_get_members(self):
        """获取成员列表"""
        self._print_section("6. 获取租户成员列表")

        response = requests.get(
            f"{self.api_base}/iam/members",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-Id": str(self.tenant_id),
            },
        )

        if response.status_code != 200:
            self._print_error(f"获取成员列表失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取成员列表成功")
        return True

    def test_get_resource_tree(self):
        """获取资源树"""
        self._print_section("7. 获取资源树 (TABLE scope)")

        response = requests.get(
            f"{self.api_base}/resource-tree",
            params={"scope": "TABLE"},
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-Id": str(self.tenant_id),
            },
        )

        if response.status_code != 200:
            self._print_error(f"获取资源树失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取资源树成功")
        return True

    def test_get_permissions(self):
        """获取当前用户权限"""
        self._print_section("8. 获取当前用户的权限信息")

        response = requests.get(
            f"{self.api_base}/iam/permissions/me",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-Id": str(self.tenant_id),
            },
        )

        if response.status_code != 200:
            self._print_error(f"获取权限信息失败: {response.status_code}")
            self._print_json(response.json())
            return False

        data = response.json()
        self._print_json(data)
        self._print_success("获取权限信息成功")
        return True

    def test_logout(self):
        """测试登出"""
        self._print_section("9. 用户登出")

        response = requests.post(
            f"{self.api_base}/auth/logout",
            headers={"Authorization": f"Bearer {self.access_token}"},
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
            self.test_get_members,
            self.test_get_resource_tree,
            self.test_get_permissions,
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
