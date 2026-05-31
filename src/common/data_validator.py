"""
数据验证器模块
遵循第一性原理：数据完整性公理

核心功能：
1. Schema验证 - 基于结构定义的数据验证
2. 类型检查 - 运行时类型校验
3. 约束验证 - 范围、长度、格式等约束
4. 自定义验证规则 - 可扩展的验证器注册
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class ValidationError(Exception):
    """验证错误"""
    def __init__(self, message: str, field: str = "", code: str = ""):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)

    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "code": self.code,
        }


class ValidationResult:
    """验证结果"""

    def __init__(self):
        self._errors: List[ValidationError] = []
        self._is_valid = True

    def add_error(self, error: ValidationError) -> None:
        self._errors.append(error)
        self._is_valid = False

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    @property
    def errors(self) -> List[ValidationError]:
        return self._errors.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self._is_valid,
            "errors": [e.to_dict() for e in self._errors],
        }

    def raise_if_invalid(self) -> None:
        if not self._is_valid:
            raise ValidationError(
                f"Validation failed: {'; '.join(e.message for e in self._errors)}"
            )


class Validator(ABC):
    """验证器抽象基类"""

    @abstractmethod
    def validate(self, value: Any, field: str = "") -> Optional[str]:
        """验证值，返回错误信息或None"""
        pass


class TypeValidator(Validator):
    """类型验证器"""

    def __init__(self, expected_type: Union[Type, Tuple[Type, ...]]):
        self.expected_type = expected_type

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, self.expected_type):
            type_names = self.expected_type
            if isinstance(self.expected_type, tuple):
                type_names = " | ".join(t.__name__ for t in self.expected_type)
            else:
                type_names = self.expected_type.__name__
            return f"Expected type {type_names}, got {type(value).__name__}"
        return None


class RequiredValidator(Validator):
    """必填验证器"""

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return "This field is required"
        if isinstance(value, str) and value.strip() == "":
            return "This field is required"
        return None


class RangeValidator(Validator):
    """范围验证器"""

    def __init__(self, min_value: Optional[Any] = None, max_value: Optional[Any] = None):
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        if self.min_value is not None and value < self.min_value:
            return f"Must be >= {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return f"Must be <= {self.max_value}"
        return None


class LengthValidator(Validator):
    """长度验证器"""

    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None):
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        try:
            length = len(value)
        except TypeError:
            return "Value has no length"
        if self.min_length is not None and length < self.min_length:
            return f"Length must be >= {self.min_length}"
        if self.max_length is not None and length > self.max_length:
            return f"Length must be <= {self.max_length}"
        return None


class RegexValidator(Validator):
    """正则表达式验证器"""

    def __init__(self, pattern: str, message: Optional[str] = None):
        self.pattern = re.compile(pattern)
        self.message = message or f"Must match pattern: {pattern}"

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            return "Value must be a string"
        if not self.pattern.match(value):
            return self.message
        return None


class EmailValidator(Validator):
    """邮箱验证器"""

    _EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            return "Email must be a string"
        if not self._EMAIL_PATTERN.match(value):
            return "Invalid email format"
        return None


class ChoiceValidator(Validator):
    """选项验证器"""

    def __init__(self, choices: List[Any]):
        self.choices = choices

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        if value not in self.choices:
            return f"Must be one of: {self.choices}"
        return None


class CustomValidator(Validator):
    """自定义验证器"""

    def __init__(self, func: Callable[[Any], Optional[str]]):
        self.func = func

    def validate(self, value: Any, field: str = "") -> Optional[str]:
        if value is None:
            return None
        return self.func(value)


@dataclass
class FieldSchema:
    """字段Schema定义"""
    name: str
    validators: List[Validator] = field(default_factory=list)
    default: Any = None
    allow_none: bool = True

    def validate(self, value: Any) -> List[str]:
        """验证字段值，返回所有错误信息"""
        errors = []
        if value is None:
            if not self.allow_none:
                errors.append("This field cannot be None")
            # None值仍需经过validators检查（如RequiredValidator）
            for validator in self.validators:
                error = validator.validate(value, self.name)
                if error:
                    errors.append(error)
            return errors

        for validator in self.validators:
            error = validator.validate(value, self.name)
            if error:
                errors.append(error)
        return errors


class Schema:
    """数据Schema"""

    def __init__(self, name: str = ""):
        self.name = name
        self._fields: Dict[str, FieldSchema] = {}

    def add_field(self, field: FieldSchema) -> None:
        """添加字段定义"""
        self._fields[field.name] = field

    def field(
        self,
        name: str,
        required: bool = False,
        field_type: Optional[Type] = None,
        min_value: Optional[Any] = None,
        max_value: Optional[Any] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        choices: Optional[List[Any]] = None,
        email: bool = False,
        default: Any = None,
        allow_none: bool = True,
        custom: Optional[Callable[[Any], Optional[str]]] = None,
    ) -> Schema:
        """链式添加字段"""
        validators: List[Validator] = []

        if required:
            validators.append(RequiredValidator())
        if field_type is not None:
            validators.append(TypeValidator(field_type))
        if min_value is not None or max_value is not None:
            validators.append(RangeValidator(min_value, max_value))
        if min_length is not None or max_length is not None:
            validators.append(LengthValidator(min_length, max_length))
        if pattern is not None:
            validators.append(RegexValidator(pattern))
        if choices is not None:
            validators.append(ChoiceValidator(choices))
        if email:
            validators.append(EmailValidator())
        if custom is not None:
            validators.append(CustomValidator(custom))

        self.add_field(FieldSchema(
            name=name,
            validators=validators,
            default=default,
            allow_none=allow_none,
        ))
        return self

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """验证数据字典"""
        result = ValidationResult()

        for field_name, field_schema in self._fields.items():
            value = data.get(field_name, field_schema.default)
            errors = field_schema.validate(value)
            for error in errors:
                result.add_error(ValidationError(error, field=field_name, code="validation_error"))

        return result

    def validate_object(self, obj: Any) -> ValidationResult:
        """验证对象属性"""
        data = {}
        for field_name in self._fields:
            if hasattr(obj, field_name):
                data[field_name] = getattr(obj, field_name)
        return self.validate(data)


class DataValidator:
    """
    数据验证器

    统一管理所有Schema和自定义验证规则
    """

    def __init__(self):
        self._schemas: Dict[str, Schema] = {}
        self._custom_rules: Dict[str, Callable[[Any], Optional[str]]] = {}

    def register_schema(self, name: str, schema: Schema) -> None:
        """注册Schema"""
        self._schemas[name] = schema
        logger.info(f"注册Schema: {name}")

    def register_rule(self, name: str, rule: Callable[[Any], Optional[str]]) -> None:
        """注册自定义验证规则"""
        self._custom_rules[name] = rule
        logger.info(f"注册自定义规则: {name}")

    def validate(self, schema_name: str, data: Dict[str, Any]) -> ValidationResult:
        """使用指定Schema验证数据"""
        schema = self._schemas.get(schema_name)
        if schema is None:
            result = ValidationResult()
            result.add_error(ValidationError(f"Schema not found: {schema_name}", code="schema_not_found"))
            return result
        return schema.validate(data)

    def validate_with_rule(self, rule_name: str, value: Any) -> Optional[str]:
        """使用自定义规则验证单个值"""
        rule = self._custom_rules.get(rule_name)
        if rule is None:
            return f"Rule not found: {rule_name}"
        return rule(value)

    def quick_validate(self, value: Any, *validators: Validator) -> ValidationResult:
        """快速验证单个值"""
        result = ValidationResult()
        for validator in validators:
            error = validator.validate(value)
            if error:
                result.add_error(ValidationError(error))
        return result


def demo_data_validator():
    """演示数据验证器"""
    print("=" * 60)
    print("数据验证器演示")
    print("=" * 60)
    print()

    # 1. 类型检查
    print("1. 类型检查:")
    tv = TypeValidator((int, float))
    print(f"   42 -> {tv.validate(42) or '通过'}")
    print(f"   '42' -> {tv.validate('42') or '通过'}")
    print()

    # 2. 范围验证
    print("2. 范围验证:")
    rv = RangeValidator(min_value=0, max_value=100)
    print(f"   50 -> {rv.validate(50) or '通过'}")
    print(f"   150 -> {rv.validate(150) or '通过'}")
    print()

    # 3. 长度验证
    print("3. 长度验证:")
    lv = LengthValidator(min_length=3, max_length=10)
    print(f"   'hello' -> {lv.validate('hello') or '通过'}")
    print(f"   'hi' -> {lv.validate('hi') or '通过'}")
    print()

    # 4. 正则验证
    print("4. 正则验证:")
    rev = RegexValidator(r"^\d{4}-\d{2}-\d{2}$", "Must be YYYY-MM-DD format")
    print(f"   '2024-01-15' -> {rev.validate('2024-01-15') or '通过'}")
    print(f"   '01-15-2024' -> {rev.validate('01-15-2024') or '通过'}")
    print()

    # 5. 邮箱验证
    print("5. 邮箱验证:")
    ev = EmailValidator()
    print(f"   'test@example.com' -> {ev.validate('test@example.com') or '通过'}")
    print(f"   'invalid-email' -> {ev.validate('invalid-email') or '通过'}")
    print()

    # 6. Schema验证
    print("6. Schema验证:")
    user_schema = Schema("user")
    user_schema.field("username", required=True, field_type=str, min_length=3, max_length=20)
    user_schema.field("age", required=True, field_type=int, min_value=0, max_value=150)
    user_schema.field("email", required=True, email=True)
    user_schema.field("role", choices=["admin", "user", "guest"])

    valid_data = {
        "username": "alice",
        "age": 25,
        "email": "alice@example.com",
        "role": "admin",
    }
    result = user_schema.validate(valid_data)
    print(f"   有效数据 -> {'通过' if result.is_valid else '失败'}")

    invalid_data = {
        "username": "ab",
        "age": 200,
        "email": "not-an-email",
        "role": "superuser",
    }
    result = user_schema.validate(invalid_data)
    print(f"   无效数据 -> {'通过' if result.is_valid else '失败'}")
    for error in result.errors:
        print(f"     - {error.field}: {error.message}")
    print()

    # 7. 数据验证器管理
    print("7. 数据验证器管理:")
    validator = DataValidator()
    validator.register_schema("user", user_schema)
    validator.register_rule("positive", lambda x: None if (isinstance(x, (int, float)) and x > 0) else "Must be positive")

    result = validator.validate("user", valid_data)
    print(f"   验证结果: {result.to_dict()}")

    rule_result = validator.validate_with_rule("positive", 10)
    print(f"   正数规则(10): {rule_result or '通过'}")
    rule_result = validator.validate_with_rule("positive", -5)
    print(f"   正数规则(-5): {rule_result or '通过'}")
    print()

    print("=" * 60)
    print("数据验证器演示完成")
    print("=" * 60)
    print()
    print("✓ Schema验证")
    print("✓ 类型检查")
    print("✓ 约束验证")
    print("✓ 自定义验证规则")
    print()


if __name__ == "__main__":
    demo_data_validator()
