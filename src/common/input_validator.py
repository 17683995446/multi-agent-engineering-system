"""
输入验证模块
遵循第一性原理：信息最小熵公理

核心功能：
1. SQL注入检测
2. XSS检测
3. 路径遍历检测
4. 命令注入检测
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class ThreatType(Enum):
    """威胁类型"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    SAFE = "safe"


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    threat_type: ThreatType = ThreatType.SAFE
    message: str = ""
    matched_pattern: Optional[str] = None
    risk_level: str = "low"


class SQLInjectionDetector:
    """SQL注入检测器"""

    PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b.*\b(FROM|INTO|TABLE|DATABASE)\b)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
        r"('.*'\s*OR\s*'.*'\s*=\s*'.*')",
        r"(--|#|/\*|\*/)",
        r"(\bWAITFOR\b\s+\bDELAY\b)",
        r"(\bBENCHMARK\b\s*\()",
        r"(1\s*=\s*1)",
        r"('\s*OR\s*'1'\s*=\s*'1)",
        r"(;\s*\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b)",
    ]

    @classmethod
    def detect(cls, input_value: Union[str, Any]) -> ValidationResult:
        """检测SQL注入"""
        if not isinstance(input_value, str):
            return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)

        for pattern in cls.PATTERNS:
            match = re.search(pattern, input_value, re.IGNORECASE)
            if match:
                return ValidationResult(
                    is_valid=False,
                    threat_type=ThreatType.SQL_INJECTION,
                    message=f"检测到SQL注入攻击",
                    matched_pattern=match.group(0),
                    risk_level="high",
                )
        return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)


class XSSDetector:
    """XSS检测器"""

    PATTERNS = [
        r"(<script[^>]*>.*?</script>)",
        r"(javascript:\s*)",
        r"(on\w+\s*=\s*['\"]?[^'\"\s>]+)",
        r"(<\s*iframe[^>]*>)",
        r"(<\s*object[^>]*>)",
        r"(<\s*embed[^>]*>)",
        r"(eval\s*\()",
        r"(expression\s*\()",
        r"(<\s*img[^>]*onerror\s*=)",
        r"(alert\s*\()",
        r"(document\.cookie)",
        r"(document\.location)",
        r"(window\.location)",
    ]

    @classmethod
    def detect(cls, input_value: Union[str, Any]) -> ValidationResult:
        """检测XSS攻击"""
        if not isinstance(input_value, str):
            return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)

        for pattern in cls.PATTERNS:
            match = re.search(pattern, input_value, re.IGNORECASE)
            if match:
                return ValidationResult(
                    is_valid=False,
                    threat_type=ThreatType.XSS,
                    message=f"检测到XSS攻击",
                    matched_pattern=match.group(0),
                    risk_level="high",
                )
        return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)


class PathTraversalDetector:
    """路径遍历检测器"""

    PATTERNS = [
        r"(\.\./)",
        r"(\.\.\\)",
        r"(\.\.//)",
        r"(%2e%2e%2f)",
        r"(%2e%2e/)",
        r"(\.\.(%2f|%5c))",
        r"(\.\%00\.)",
        r"(\\\.\\)",
        r"(/etc/passwd)",
        r"(C:\\Windows)",
        r"(/proc/self)",
        r"(\\.\\.\\)",
    ]

    @classmethod
    def detect(cls, input_value: Union[str, Any]) -> ValidationResult:
        """检测路径遍历攻击"""
        if not isinstance(input_value, str):
            return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)

        for pattern in cls.PATTERNS:
            match = re.search(pattern, input_value, re.IGNORECASE)
            if match:
                return ValidationResult(
                    is_valid=False,
                    threat_type=ThreatType.PATH_TRAVERSAL,
                    message=f"检测到路径遍历攻击",
                    matched_pattern=match.group(0),
                    risk_level="high",
                )
        return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)


class CommandInjectionDetector:
    """命令注入检测器"""

    PATTERNS = [
        r"([;&|]\s*\b(cat|ls|pwd|whoami|id|uname|echo|bash|sh|cmd|powershell|python|ruby|perl)\b)",
        r"(\$\(.*\))",
        r"(`.*`)",
        r"(\|\s*\b(sh|bash|cmd)\b)",
        r"(>\s*/\w+)",
        r"(<\s*/\w+)",
        r"(\bnc\b\s+-[el])",
        r"(\bcurl\b.*\||\bwget\b.*\|)",
        r"(2>&1)",
        r"(/dev/tcp/)",
        r"(/dev/udp/)",
    ]

    @classmethod
    def detect(cls, input_value: Union[str, Any]) -> ValidationResult:
        """检测命令注入攻击"""
        if not isinstance(input_value, str):
            return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)

        for pattern in cls.PATTERNS:
            match = re.search(pattern, input_value, re.IGNORECASE)
            if match:
                return ValidationResult(
                    is_valid=False,
                    threat_type=ThreatType.COMMAND_INJECTION,
                    message=f"检测到命令注入攻击",
                    matched_pattern=match.group(0),
                    risk_level="critical",
                )
        return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)


class InputValidator:
    """输入验证器 - 整合所有检测功能"""

    DETECTORS = [
        SQLInjectionDetector,
        XSSDetector,
        PathTraversalDetector,
        CommandInjectionDetector,
    ]

    def __init__(self):
        self.logger = setup_logger(__name__ + ".InputValidator")

    def validate(self, input_value: Union[str, Any]) -> ValidationResult:
        """全面验证输入"""
        for detector in self.DETECTORS:
            result = detector.detect(input_value)
            if not result.is_valid:
                self.logger.warning(f"输入验证失败: {result.threat_type.value} - {result.message}")
                return result
        return ValidationResult(is_valid=True, threat_type=ThreatType.SAFE)

    def validate_multiple(self, inputs: Dict[str, Any]) -> Dict[str, ValidationResult]:
        """批量验证多个输入"""
        results = {}
        for key, value in inputs.items():
            results[key] = self.validate(value)
        return results

    def is_safe(self, input_value: Union[str, Any]) -> bool:
        """快速判断输入是否安全"""
        return self.validate(input_value).is_valid

    def sanitize(self, input_value: str) -> str:
        """清理输入中的危险字符"""
        sanitized = input_value
        sanitized = re.sub(r"[<>]", "", sanitized)
        sanitized = re.sub(r"['\";|&`$]", "", sanitized)
        sanitized = re.sub(r"\\.\\./", "", sanitized)
        sanitized = re.sub(r"\\.\\.\\\\", "", sanitized)
        return sanitized

    def get_threat_summary(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """获取威胁摘要"""
        results = self.validate_multiple(inputs)
        threats = [r for r in results.values() if not r.is_valid]
        return {
            "total": len(inputs),
            "safe": len(inputs) - len(threats),
            "threats": len(threats),
            "threat_types": list(set(t.threat_type.value for t in threats)),
            "risk_levels": list(set(t.risk_level for t in threats)),
        }
