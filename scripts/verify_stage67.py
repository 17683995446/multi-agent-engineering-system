#!/usr/bin/env python3
"""
阶段67验证脚本：数据验证器

测试内容：
1. Schema验证
2. 类型检查
3. 约束验证（范围、长度、正则）
4. 自定义验证规则
5. 验证结果处理
6. 对象验证
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.data_validator import (
    ChoiceValidator,
    CustomValidator,
    DataValidator,
    EmailValidator,
    FieldSchema,
    LengthValidator,
    RangeValidator,
    RegexValidator,
    RequiredValidator,
    Schema,
    TypeValidator,
    ValidationError,
    ValidationResult,
)


def test_schema_validation() -> bool:
    print("[Test] Schema验证")
    try:
        user_schema = Schema("user")
        user_schema.field("username", required=True, field_type=str, min_length=3, max_length=20)
        user_schema.field("age", required=True, field_type=int, min_value=0, max_value=150)
        user_schema.field("email", required=True, email=True)
        user_schema.field("role", choices=["admin", "user", "guest"])

        # 有效数据
        valid_data = {
            "username": "alice",
            "age": 25,
            "email": "alice@example.com",
            "role": "admin",
        }
        result = user_schema.validate(valid_data)
        assert result.is_valid
        assert len(result.errors) == 0
        print("  ✓ 有效数据通过验证")

        # 无效数据
        invalid_data = {
            "username": "ab",
            "age": 200,
            "email": "not-an-email",
            "role": "superuser",
        }
        result = user_schema.validate(invalid_data)
        assert not result.is_valid
        assert len(result.errors) == 4
        print(f"  ✓ 无效数据检测到4个错误")

        # 缺少必填字段
        incomplete_data = {"username": "bob"}
        result = user_schema.validate(incomplete_data)
        assert not result.is_valid
        assert any(e.field == "age" for e in result.errors)
        assert any(e.field == "email" for e in result.errors)
        # age和email是required字段，role不是required所以不报错
        assert len(result.errors) == 2
        print(f"  ✓ 缺少必填字段被检测 ({len(result.errors)}个错误)")

        print("[Pass] Schema验证\n")
        return True
    except Exception as e:
        print(f"[Fail] Schema验证: {e}\n")
        return False


def test_type_check() -> bool:
    print("[Test] 类型检查")
    try:
        tv_int = TypeValidator(int)
        assert tv_int.validate(42) is None
        assert tv_int.validate("42") is not None
        assert tv_int.validate(None) is None
        print("  ✓ int类型验证正确")

        tv_union = TypeValidator((int, float))
        assert tv_union.validate(42) is None
        assert tv_union.validate(3.14) is None
        assert tv_union.validate("42") is not None
        print("  ✓ union类型验证正确")

        tv_str = TypeValidator(str)
        assert tv_str.validate("hello") is None
        assert tv_str.validate(123) is not None
        print("  ✓ str类型验证正确")

        # Schema级别类型检查
        schema = Schema("typed")
        schema.field("count", field_type=int)
        schema.field("name", field_type=str)

        result = schema.validate({"count": 10, "name": "test"})
        assert result.is_valid
        print("  ✓ Schema类型检查通过")

        result = schema.validate({"count": "10", "name": 123})
        assert not result.is_valid
        assert len(result.errors) == 2
        print("  ✓ Schema类型错误检测")

        print("[Pass] 类型检查\n")
        return True
    except Exception as e:
        print(f"[Fail] 类型检查: {e}\n")
        return False


def test_constraint_validation() -> bool:
    print("[Test] 约束验证")
    try:
        # 范围验证
        rv = RangeValidator(min_value=0, max_value=100)
        assert rv.validate(50) is None
        assert rv.validate(0) is None
        assert rv.validate(100) is None
        assert rv.validate(-1) is not None
        assert rv.validate(101) is not None
        print("  ✓ 范围验证正确")

        # 长度验证
        lv = LengthValidator(min_length=3, max_length=10)
        assert lv.validate("hello") is None
        assert lv.validate("hi") is not None
        assert lv.validate("a" * 11) is not None
        assert lv.validate([1, 2, 3]) is None
        print("  ✓ 长度验证正确")

        # 正则验证
        rev = RegexValidator(r"^\d{4}-\d{2}-\d{2}$")
        assert rev.validate("2024-01-15") is None
        assert rev.validate("01-15-2024") is not None
        assert rev.validate(123) is not None
        print("  ✓ 正则验证正确")

        # 邮箱验证
        ev = EmailValidator()
        assert ev.validate("test@example.com") is None
        assert ev.validate("invalid") is not None
        assert ev.validate("@example.com") is not None
        print("  ✓ 邮箱验证正确")

        # 选项验证
        cv = ChoiceValidator(["a", "b", "c"])
        assert cv.validate("a") is None
        assert cv.validate("d") is not None
        print("  ✓ 选项验证正确")

        # 必填验证
        reqv = RequiredValidator()
        assert reqv.validate("value") is None
        assert reqv.validate(None) is not None
        assert reqv.validate("  ") is not None
        print("  ✓ 必填验证正确")

        print("[Pass] 约束验证\n")
        return True
    except Exception as e:
        print(f"[Fail] 约束验证: {e}\n")
        return False


def test_custom_rules() -> bool:
    print("[Test] 自定义验证规则")
    try:
        # 自定义验证器
        def is_even(value):
            if isinstance(value, int) and value % 2 == 0:
                return None
            return "Must be even"

        cv = CustomValidator(is_even)
        assert cv.validate(4) is None
        assert cv.validate(5) is not None
        print("  ✓ 自定义验证器正确")

        # Schema中使用自定义验证
        schema = Schema("even_number")
        schema.field("value", field_type=int, custom=is_even)

        result = schema.validate({"value": 8})
        assert result.is_valid
        print("  ✓ Schema自定义验证通过")

        result = schema.validate({"value": 7})
        assert not result.is_valid
        print("  ✓ Schema自定义验证拒绝")

        # DataValidator自定义规则
        dv = DataValidator()
        dv.register_rule("positive", lambda x: None if (isinstance(x, (int, float)) and x > 0) else "Must be positive")
        dv.register_rule("non_empty_list", lambda x: None if (isinstance(x, list) and len(x) > 0) else "Must be non-empty list")

        assert dv.validate_with_rule("positive", 10) is None
        assert dv.validate_with_rule("positive", -5) is not None
        print("  ✓ DataValidator规则注册与验证")

        assert dv.validate_with_rule("non_empty_list", [1, 2]) is None
        assert dv.validate_with_rule("non_empty_list", []) is not None
        print("  ✓ 列表非空规则验证")

        # 规则不存在
        assert dv.validate_with_rule("not_exist", 1) is not None
        print("  ✓ 不存在的规则返回错误")

        print("[Pass] 自定义验证规则\n")
        return True
    except Exception as e:
        print(f"[Fail] 自定义验证规则: {e}\n")
        return False


def test_validation_result() -> bool:
    print("[Test] 验证结果处理")
    try:
        result = ValidationResult()
        assert result.is_valid
        assert len(result.errors) == 0
        print("  ✓ 空结果有效")

        result.add_error(ValidationError("Error 1", field="f1"))
        assert not result.is_valid
        assert len(result.errors) == 1
        print("  ✓ 添加错误后无效")

        result.add_error(ValidationError("Error 2", field="f2"))
        assert len(result.errors) == 2
        print("  ✓ 多个错误记录")

        # to_dict
        d = result.to_dict()
        assert d["is_valid"] is False
        assert len(d["errors"]) == 2
        print("  ✓ to_dict正确")

        # raise_if_invalid
        try:
            result.raise_if_invalid()
            assert False, "应该抛出异常"
        except ValidationError:
            print("  ✓ raise_if_invalid抛出异常")

        # 有效结果不抛出
        valid_result = ValidationResult()
        valid_result.raise_if_invalid()
        print("  ✓ 有效结果不抛出异常")

        print("[Pass] 验证结果处理\n")
        return True
    except Exception as e:
        print(f"[Fail] 验证结果处理: {e}\n")
        return False


def test_object_validation() -> bool:
    print("[Test] 对象验证")
    try:
        class User:
            def __init__(self, username, age, email):
                self.username = username
                self.age = age
                self.email = email

        schema = Schema("user_obj")
        schema.field("username", required=True, field_type=str, min_length=3)
        schema.field("age", required=True, field_type=int, min_value=0)
        schema.field("email", required=True, email=True)

        user = User("alice", 25, "alice@example.com")
        result = schema.validate_object(user)
        assert result.is_valid
        print("  ✓ 有效对象通过验证")

        bad_user = User("ab", -1, "invalid")
        result = schema.validate_object(bad_user)
        assert not result.is_valid
        assert len(result.errors) == 3
        print("  ✓ 无效对象检测到3个错误")

        print("[Pass] 对象验证\n")
        return True
    except Exception as e:
        print(f"[Fail] 对象验证: {e}\n")
        return False


def test_data_validator_manager() -> bool:
    print("[Test] DataValidator管理器")
    try:
        dv = DataValidator()

        schema = Schema("product")
        schema.field("name", required=True, field_type=str, min_length=1)
        schema.field("price", required=True, field_type=(int, float), min_value=0)

        dv.register_schema("product", schema)

        # 验证成功
        result = dv.validate("product", {"name": "Book", "price": 29.99})
        assert result.is_valid
        print("  ✓ 管理器Schema验证通过")

        # 验证失败
        result = dv.validate("product", {"name": "", "price": -5})
        assert not result.is_valid
        print("  ✓ 管理器Schema验证拒绝")

        # Schema不存在
        result = dv.validate("not_exist", {})
        assert not result.is_valid
        assert any("Schema not found" in e.message for e in result.errors)
        print("  ✓ 不存在的Schema返回错误")

        # quick_validate
        result = dv.quick_validate("hello", RequiredValidator(), LengthValidator(min_length=3))
        assert result.is_valid
        print("  ✓ quick_validate通过")

        result = dv.quick_validate("", RequiredValidator())
        assert not result.is_valid
        print("  ✓ quick_validate拒绝")

        print("[Pass] DataValidator管理器\n")
        return True
    except Exception as e:
        print(f"[Fail] DataValidator管理器: {e}\n")
        return False


def test_allow_none() -> bool:
    print("[Test] allow_none控制")
    try:
        schema = Schema("nullable")
        schema.field("optional", field_type=str, allow_none=True)
        schema.field("required_str", field_type=str, allow_none=False)

        result = schema.validate({"optional": None, "required_str": "value"})
        assert result.is_valid
        print("  ✓ allow_none=True允许None")

        result = schema.validate({"optional": None, "required_str": None})
        assert not result.is_valid
        assert any("cannot be None" in e.message for e in result.errors)
        print("  ✓ allow_none=False拒绝None")

        print("[Pass] allow_none控制\n")
        return True
    except Exception as e:
        print(f"[Fail] allow_none控制: {e}\n")
        return False


def main() -> int:
    print("=" * 60)
    print("阶段67验证脚本：数据验证器")
    print("=" * 60 + "\n")

    results = []
    results.append(("Schema验证", test_schema_validation()))
    results.append(("类型检查", test_type_check()))
    results.append(("约束验证", test_constraint_validation()))
    results.append(("自定义验证规则", test_custom_rules()))
    results.append(("验证结果处理", test_validation_result()))
    results.append(("对象验证", test_object_validation()))
    results.append(("DataValidator管理器", test_data_validator_manager()))
    results.append(("allow_none控制", test_allow_none()))

    print("=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("🎉 所有测试通过！阶段67验收成功。")
        return 0
    else:
        print("⚠️ 存在失败的测试，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
