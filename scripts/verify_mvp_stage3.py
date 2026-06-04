#!/usr/bin/env python3
"""
MVP阶段3验证脚本: 代码原子扫描器
测试四级原子化检查功能。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.mvp_core.atom_scanner import (
    VariableAtomScanner,
    MethodAtomScanner,
    ClassAtomScanner,
    ModuleAtomScanner,
    UnifiedAtomScanner,
    IssueSeverity,
)


# ==================== 测试用例代码 ====================

GOOD_VARIABLE_CODE = '''
MAX_SIZE = 100
DEBUG_MODE = True

is_running = False
has_error = False

user_id = 123
user_name = "test"
email_address = "test@example.com"
'''

BAD_VARIABLE_CODE = '''
maxSize = 100
Data = {}
result = 0
x = 10
TEMP_VAL = 1
'''

GOOD_METHOD_CODE = '''
def validate_user(name, age):
    """验证用户数据"""
    if not name:
        raise ValueError("Name required")
    if age <= 0:
        raise ValueError("Age invalid")
    return True


def process_user(user_id):
    """处理用户"""
    user = fetch_user(user_id)
    if not user:
        return None
    data = {"id": user.id, "name": user.name}
    return data
'''

BAD_METHOD_CODE = '''
def user_data(name, age, email, address, phone, status, extra):
    if not name:
        raise ValueError("Name required")
    if not age:
        raise ValueError("Age required")
    if not email:
        raise ValueError("Email required")
    if not address:
        raise ValueError("Address required")
    if not phone:
        raise ValueError("Phone required")
    if not status:
        raise ValueError("Status required")
    if not extra:
        raise ValueError("Extra required")
    data = {}
    data["name"] = name
    data["age"] = age
    data["email"] = email
    data["address"] = address
    data["phone"] = phone
    data["status"] = status
    data["extra"] = extra
    if status == "active":
        send_email(email)
    elif status == "pending":
        verify_email(email)
    if age > 18:
        apply_discount(data)
    if address:
        validate_address(address)
    save_to_db(data)
    cache_data(data)
    return data
'''

GOOD_CLASS_CODE = '''
class UserService:
    """用户服务"""

    MAX_RETRY = 3
    DEFAULT_TIMEOUT = 30

    _users = {}
    _cache = None

    def get_user(self, user_id):
        return self._users.get(user_id)

    def create_user(self, user_data):
        self._users[user_data["id"]] = user_data
        return user_data

    def update_user(self, user_id, data):
        if user_id in self._users:
            self._users[user_id].update(data)
        return self._users[user_id]

    def delete_user(self, user_id):
        return self._users.pop(user_id, None)
'''

BAD_CLASS_CODE = '''
class bad_class:
    """问题类"""

    def method1(self):
        pass

    MAX_VALUE = 100
    _count = 0

    def method2(self):
        pass

    def get_user(self, user_id):
        pass

    def create_order(self, order_data):
        pass

    def send_email(self, email):
        pass

    def calculate_price(self, items):
        pass

    def render_page(self, template):
        pass

    def log_event(self, event):
        pass

    def validate_input(self, data):
        pass

    def fetch_data(self, url):
        pass

    def save_file(self, path, content):
        pass

    def process_image(self, image):
        pass

    def encrypt_data(self, data):
        pass

    def decrypt_data(self, data):
        pass

    def send_request(self, req):
        pass

    def parse_response(self, resp):
        pass

    def build_query(self, params):
        pass

    def execute_query(self, query):
        pass

    def format_result(self, result):
        pass
'''

GOOD_MODULE_CODE = '''
"""良好的模块示例"""

__all__ = ["UserService", "get_user", "create_user"]

from typing import Dict, Optional


class UserService:
    """用户服务"""

    def get_user(self, user_id: str) -> Optional[Dict]:
        pass

    def create_user(self, user_data: Dict) -> str:
        pass


def get_user(user_id: str) -> Optional[Dict]:
    service = UserService()
    return service.get_user(user_id)


def create_user(user_data: Dict) -> str:
    service = UserService()
    return service.create_user(user_data)


def _validate_user_data(data: Dict) -> bool:
    return "name" in data


if __name__ == "__main__":
    pass
'''

BAD_MODULE_CODE = '''
"""问题模块示例"""

import os
import sys
import json

class UserService:
    pass

class OrderService:
    pass

class ProductService:
    pass

class InventoryService:
    pass

class PaymentService:
    pass

class ShippingService:
    pass

class NotificationService:
    pass

class ReportService:
    pass

class AnalyticsService:
    pass

class ConfigService:
    pass

class SettingsService:
    pass

def func1(): pass
def func2(): pass
def func3(): pass
def func4(): pass
def func5(): pass
def func6(): pass
def func7(): pass
def func8(): pass
def func9(): pass
def func10(): pass
def func11(): pass
def func12(): pass
def func13(): pass
def func14(): pass
def func15(): pass
def func16(): pass
def func17(): pass
def func18(): pass
def func19(): pass
def func20(): pass
def func21(): pass
def func22(): pass
def func23(): pass
def func24(): pass
def func25(): pass
def func26(): pass
def func27(): pass
def func28(): pass
def func29(): pass
def func30(): pass
def func31(): pass
def func32(): pass

print("loaded")
'''


# ==================== 测试函数 ====================

def test_variable_naming_good():
    """测试变量命名规范 - 良好代码"""
    print("\n[Test] 变量命名规范检测 - 良好代码")
    scanner = VariableAtomScanner()
    result = scanner.scan(GOOD_VARIABLE_CODE)

    assert result.passed, f"期望通过，但失败: {[i.message for i in result.issues]}"
    assert result.metrics["total_variables"] >= 4
    print(f"  ✓ 变量总数: {result.metrics['total_variables']}")
    print(f"  ✓ 常量数: {result.metrics.get('constant_count', 0)}")
    print(f"  ✓ 无命名违规")
    print("[Pass] 变量命名规范检测 - 良好代码\n")
    return True


def test_variable_naming_bad():
    """测试变量命名规范 - 问题代码"""
    print("[Test] 变量命名规范检测 - 问题代码")
    scanner = VariableAtomScanner()
    result = scanner.scan(BAD_VARIABLE_CODE)

    issue_types = [i.issue_type for i in result.issues]
    assert "naming_violation" in issue_types or "vague_naming" in issue_types or "constant_naming" in issue_types
    print(f"  ✓ 检测到 {len(result.issues)} 个问题")
    for issue in result.issues:
        print(f"    - {issue.issue_type}: {issue.message}")
    print("[Pass] 变量命名规范检测 - 问题代码\n")
    return True


def test_method_four_section_good():
    """测试方法四段式 - 良好代码"""
    print("[Test] 方法四段式检测 - 良好代码")
    scanner = MethodAtomScanner()
    result = scanner.scan(GOOD_METHOD_CODE)

    assert result.passed, f"期望通过，但失败: {[i.message for i in result.issues]}"
    assert result.metrics["total_methods"] == 2
    print(f"  ✓ 方法总数: {result.metrics['total_methods']}")
    print(f"  ✓ 平均行数: {result.metrics.get('avg_lines', 0):.1f}")
    print("[Pass] 方法四段式检测 - 良好代码\n")
    return True


def test_method_four_section_bad():
    """测试方法四段式 - 问题代码"""
    print("[Test] 方法四段式检测 - 问题代码")
    scanner = MethodAtomScanner()
    result = scanner.scan(BAD_METHOD_CODE)

    issue_types = [i.issue_type for i in result.issues]
    assert "too_long" in issue_types, f"期望检测到方法过长，实际: {issue_types}"
    assert "too_many_params" in issue_types, f"期望检测到参数过多，实际: {issue_types}"
    print(f"  ✓ 检测到 {len(result.issues)} 个问题")
    for issue in result.issues:
        print(f"    - {issue.issue_type}: {issue.message}")
    print("[Pass] 方法四段式检测 - 问题代码\n")
    return True


def test_class_single_responsibility_good():
    """测试类单一职责 - 良好代码"""
    print("[Test] 类单一职责检测 - 良好代码")
    scanner = ClassAtomScanner()
    result = scanner.scan(GOOD_CLASS_CODE)

    assert result.passed, f"期望通过，但失败: {[i.message for i in result.issues]}"
    assert result.metrics["total_classes"] == 1
    print(f"  ✓ 类总数: {result.metrics['total_classes']}")
    print("  ✓ 区域顺序正确")
    print("[Pass] 类单一职责检测 - 良好代码\n")
    return True


def test_class_single_responsibility_bad():
    """测试类单一职责 - 问题代码"""
    print("[Test] 类单一职责检测 - 问题代码")
    scanner = ClassAtomScanner()
    result = scanner.scan(BAD_CLASS_CODE)

    issue_types = [i.issue_type for i in result.issues]
    assert "class_naming" in issue_types, f"期望检测到类命名问题，实际: {issue_types}"
    assert "zone_order" in issue_types, f"期望检测到区域顺序问题，实际: {issue_types}"
    assert "too_many_methods" in issue_types, f"期望检测到方法过多，实际: {issue_types}"
    print(f"  ✓ 检测到 {len(result.issues)} 个问题")
    for issue in result.issues:
        print(f"    - {issue.issue_type}: {issue.message}")
    print("[Pass] 类单一职责检测 - 问题代码\n")
    return True


def test_module_structure_good():
    """测试模块结构 - 良好代码"""
    print("[Test] 模块结构检测 - 良好代码")
    scanner = ModuleAtomScanner()
    result = scanner.scan(GOOD_MODULE_CODE, "good_module")

    assert result.passed, f"期望通过，但失败: {[i.message for i in result.issues]}"
    assert result.metrics["public_api_count"] > 0
    print(f"  ✓ 行数: {result.metrics['lines_count']}")
    print(f"  ✓ 公共API: {result.metrics['public_api_count']}")
    print("[Pass] 模块结构检测 - 良好代码\n")
    return True


def test_module_structure_bad():
    """测试模块结构 - 问题代码"""
    print("[Test] 模块结构检测 - 问题代码")
    scanner = ModuleAtomScanner()
    result = scanner.scan(BAD_MODULE_CODE, "bad_module")

    issue_types = [i.issue_type for i in result.issues]
    assert "too_many_classes" in issue_types, f"期望检测到类数过多，实际: {issue_types}"
    assert "too_many_functions" in issue_types, f"期望检测到函数数过多，实际: {issue_types}"
    assert "missing_all" in issue_types, f"期望检测到缺少 __all__，实际: {issue_types}"
    assert "execution_zone" in issue_types, f"期望检测到顶层执行代码，实际: {issue_types}"
    print(f"  ✓ 检测到 {len(result.issues)} 个问题")
    for issue in result.issues:
        print(f"    - {issue.issue_type}: {issue.message}")
    print("[Pass] 模块结构检测 - 问题代码\n")
    return True


def test_unified_scanner():
    """测试综合扫描器"""
    print("[Test] 综合扫描器")
    scanner = UnifiedAtomScanner()

    combined_code = GOOD_VARIABLE_CODE + "\n" + GOOD_METHOD_CODE + "\n" + GOOD_CLASS_CODE + "\n"
    result = scanner.scan_source(combined_code, "test_module")

    assert "variable" in result
    assert "method" in result
    assert "class" in result
    assert "module" in result

    print(f"  ✓ 变量扫描: {result['variable'].metrics}")
    print(f"  ✓ 方法扫描: {result['method'].metrics}")
    print(f"  ✓ 类扫描: {result['class'].metrics}")
    print(f"  ✓ 模块扫描: {result['module'].metrics}")
    print("[Pass] 综合扫描器\n")
    return True


def test_scan_existing_mvp_core():
    """扫描现有 MVP 核心模块"""
    print("[Test] 扫描现有 MVP 核心模块")
    scanner = UnifiedAtomScanner()

    mvp_core_dir = os.path.join(os.path.dirname(__file__), "..", "src", "mvp_core")
    if os.path.isdir(mvp_core_dir):
        results = scanner.scan_directory(mvp_core_dir)
        total_files = len(results)
        print(f"  ✓ 扫描文件数: {total_files}")
        for path, result in results.items():
            fname = os.path.basename(path)
            v_issues = len(result["variable"].issues)
            m_issues = len(result["method"].issues)
            c_issues = len(result["class"].issues)
            mod_issues = len(result["module"].issues)
            print(f"    {fname}: 变量{v_issues} 方法{m_issues} 类{c_issues} 模块{mod_issues}")
    else:
        print("  ⚠ MVP核心目录不存在，跳过")

    print("[Pass] 扫描现有 MVP 核心模块\n")
    return True


# ==================== 主程序 ====================

def main():
    print("=" * 60)
    print("MVP阶段3验证: 代码原子扫描器")
    print("=" * 60)

    results = []
    results.append(("变量命名规范-良好", test_variable_naming_good()))
    results.append(("变量命名规范-问题", test_variable_naming_bad()))
    results.append(("方法四段式-良好", test_method_four_section_good()))
    results.append(("方法四段式-问题", test_method_four_section_bad()))
    results.append(("类单一职责-良好", test_class_single_responsibility_good()))
    results.append(("类单一职责-问题", test_class_single_responsibility_bad()))
    results.append(("模块结构-良好", test_module_structure_good()))
    results.append(("模块结构-问题", test_module_structure_bad()))
    results.append(("综合扫描器", test_unified_scanner()))
    results.append(("扫描现有MVP核心", test_scan_existing_mvp_core()))

    print("=" * 60)
    print("验收结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 MVP阶段3验收通过！")
        return 0
    else:
        print("\n⚠️ 存在失败测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
