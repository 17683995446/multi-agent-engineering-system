"""
阶段82验证脚本：输入验证模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.input_validator import (
    CommandInjectionDetector,
    InputValidator,
    PathTraversalDetector,
    SQLInjectionDetector,
    ThreatType,
    XSSDetector,
)


def test_sql_injection_detected():
    """测试SQL注入检测"""
    malicious = "1' OR '1'='1"
    result = SQLInjectionDetector.detect(malicious)
    assert result.is_valid is False
    assert result.threat_type == ThreatType.SQL_INJECTION
    assert result.risk_level == "high"
    print("✓ SQL注入检测测试通过")


def test_sql_injection_union():
    """测试UNION注入检测"""
    malicious = "1 UNION SELECT * FROM users"
    result = SQLInjectionDetector.detect(malicious)
    assert result.is_valid is False
    print("✓ UNION注入检测测试通过")


def test_sql_safe():
    """测试正常SQL不被误报"""
    safe = "Hello, this is a normal text about SELECTing options"
    result = SQLInjectionDetector.detect(safe)
    assert result.is_valid is True
    print("✓ SQL安全文本测试通过")


def test_xss_script():
    """测试XSS脚本检测"""
    malicious = '<script>alert("xss")</script>'
    result = XSSDetector.detect(malicious)
    assert result.is_valid is False
    assert result.threat_type == ThreatType.XSS
    print("✓ XSS脚本检测测试通过")


def test_xss_javascript():
    """测试javascript协议检测"""
    malicious = "javascript:alert(1)"
    result = XSSDetector.detect(malicious)
    assert result.is_valid is False
    print("✓ javascript协议检测测试通过")


def test_xss_event():
    """测试事件处理器检测"""
    malicious = '<img src=x onerror=alert(1)>'
    result = XSSDetector.detect(malicious)
    assert result.is_valid is False
    print("✓ XSS事件处理器检测测试通过")


def test_xss_safe():
    """测试正常HTML不被误报"""
    safe = "<div>Hello World</div>"
    result = XSSDetector.detect(safe)
    assert result.is_valid is True
    print("✓ XSS安全文本测试通过")


def test_path_traversal():
    """测试路径遍历检测"""
    malicious = "../../../etc/passwd"
    result = PathTraversalDetector.detect(malicious)
    assert result.is_valid is False
    assert result.threat_type == ThreatType.PATH_TRAVERSAL
    print("✓ 路径遍历检测测试通过")


def test_path_traversal_windows():
    """测试Windows路径遍历"""
    malicious = "..\\\windows\\\system32"
    result = PathTraversalDetector.detect(malicious)
    assert result.is_valid is False
    print("✓ Windows路径遍历检测测试通过")


def test_path_safe():
    """测试正常路径"""
    safe = "/home/user/documents/file.txt"
    result = PathTraversalDetector.detect(safe)
    assert result.is_valid is True
    print("✓ 正常路径测试通过")


def test_command_injection():
    """测试命令注入检测"""
    malicious = "; cat /etc/passwd"
    result = CommandInjectionDetector.detect(malicious)
    assert result.is_valid is False
    assert result.threat_type == ThreatType.COMMAND_INJECTION
    assert result.risk_level == "critical"
    print("✓ 命令注入检测测试通过")


def test_command_injection_backtick():
    """测试反引号命令注入"""
    malicious = "`whoami`"
    result = CommandInjectionDetector.detect(malicious)
    assert result.is_valid is False
    print("✓ 反引号命令注入检测测试通过")


def test_command_safe():
    """测试正常命令文本"""
    safe = "This is a normal sentence with no commands"
    result = CommandInjectionDetector.detect(safe)
    assert result.is_valid is True
    print("✓ 正常命令文本测试通过")


def test_input_validator_comprehensive():
    """测试综合验证器"""
    validator = InputValidator()

    assert validator.is_safe("normal text") is True
    assert validator.is_safe("1' OR '1'='1") is False
    assert validator.is_safe('<script>alert(1)</script>') is False
    assert validator.is_safe("../../../etc/passwd") is False
    print("✓ 综合验证器测试通过")


def test_validate_multiple():
    """测试批量验证"""
    validator = InputValidator()
    inputs = {
        "name": "John Doe",
        "query": "1' OR '1'='1",
        "comment": "Nice post!",
        "path": "../../../etc/passwd",
    }
    results = validator.validate_multiple(inputs)
    assert results["name"].is_valid is True
    assert results["query"].is_valid is False
    assert results["comment"].is_valid is True
    assert results["path"].is_valid is False
    print("✓ 批量验证测试通过")


def test_sanitize():
    """测试输入清理"""
    validator = InputValidator()
    dirty = "<script>alert('xss')</script>; cat /etc/passwd"
    clean = validator.sanitize(dirty)
    assert "<script>" not in clean
    assert ";" not in clean
    print("✓ 输入清理测试通过")


def test_threat_summary():
    """测试威胁摘要"""
    validator = InputValidator()
    inputs = {
        "a": "safe",
        "b": "1' OR '1'='1",
        "c": "<script>alert(1)</script>",
        "d": "also safe",
    }
    summary = validator.get_threat_summary(inputs)
    assert summary["total"] == 4
    assert summary["safe"] == 2
    assert summary["threats"] == 2
    assert "sql_injection" in summary["threat_types"]
    assert "xss" in summary["threat_types"]
    print("✓ 威胁摘要测试通过")


def main():
    print("=" * 60)
    print("阶段82验证：输入验证模块")
    print("=" * 60)

    test_sql_injection_detected()
    test_sql_injection_union()
    test_sql_safe()
    test_xss_script()
    test_xss_javascript()
    test_xss_event()
    test_xss_safe()
    test_path_traversal()
    test_path_traversal_windows()
    test_path_safe()
    test_command_injection()
    test_command_injection_backtick()
    test_command_safe()
    test_input_validator_comprehensive()
    test_validate_multiple()
    test_sanitize()
    test_threat_summary()

    print("=" * 60)
    print("阶段82验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
