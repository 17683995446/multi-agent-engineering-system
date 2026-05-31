"""
阶段86验证脚本：安全扫描器模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.security_scanner import (
    Severity,
    ScanType,
    Vulnerability,
    ScanResult,
    DependencyScanner,
    CodeSecurityScanner,
    ConfigSecurityScanner,
    SecretLeakScanner,
    SecurityScanner,
)


def test_dependency_scan():
    """测试依赖漏洞扫描"""
    scanner = DependencyScanner()
    result = scanner.scan("django<4.2.7\nrequests<2.31.0")
    assert result.scan_type == ScanType.DEPENDENCY
    assert result.has_issues is True
    assert len(result.vulnerabilities) >= 2
    cves = [v.id for v in result.vulnerabilities]
    assert "CVE-2023-5678" in cves
    assert "CVE-2023-1234" in cves
    print("✓ 依赖漏洞扫描测试通过")


def test_dependency_parse_file():
    """测试依赖文件解析"""
    scanner = DependencyScanner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("flask<2.3.0\n")
        f.write("# comment\n")
        f.write("\n")
        f.write("django>=4.0\n")
        temp_path = f.name

    result = scanner.scan(temp_path)
    Path(temp_path).unlink()
    assert len(result.vulnerabilities) >= 1
    print("✓ 依赖文件解析测试通过")


def test_code_security_scan():
    """测试代码安全扫描"""
    scanner = CodeSecurityScanner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('import os\n')
        f.write('os.system("ls " + user_input)\n')
        f.write('password = "secret123"\n')
        f.write('debug = True\n')
        temp_path = f.name

    result = scanner.scan(temp_path)
    Path(temp_path).unlink()
    assert result.scan_type == ScanType.CODE_SECURITY
    assert result.has_issues is True
    ids = [v.id for v in result.vulnerabilities]
    assert "SEC002" in ids
    assert "SEC004" in ids
    assert "SEC006" in ids
    print("✓ 代码安全扫描测试通过")


def test_config_security_scan():
    """测试配置安全扫描"""
    scanner = ConfigSecurityScanner()
    result = scanner.scan('{"port": 3306, "csrf_enabled": false, "cors": {"allow_all": true}}')
    assert result.scan_type == ScanType.CONFIG_SECURITY
    assert result.has_issues is True
    ids = [v.id for v in result.vulnerabilities]
    assert "CFG002" in ids
    assert "CFG003" in ids
    assert "CFG004" in ids
    print("✓ 配置安全扫描测试通过")


def test_secret_leak_scan():
    """测试密钥泄露扫描"""
    scanner = SecretLeakScanner()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('aws_key = "AKIAIOSFODNN7EXAMPLE"\n')
        f.write('gh_token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"\n')
        temp_path = f.name

    result = scanner.scan(temp_path)
    Path(temp_path).unlink()
    assert result.scan_type == ScanType.SECRET_LEAK
    assert result.has_issues is True
    ids = [v.id for v in result.vulnerabilities]
    assert "LEAK001" in ids
    print("✓ 密钥泄露扫描测试通过")


def test_scan_result_properties():
    """测试扫描结果属性"""
    result = ScanResult(scan_type=ScanType.CODE_SECURITY, target="test")
    result.vulnerabilities = [
        Vulnerability("V1", "T1", "D1", Severity.CRITICAL, ScanType.CODE_SECURITY, "L1", "R1"),
        Vulnerability("V2", "T2", "D2", Severity.HIGH, ScanType.CODE_SECURITY, "L2", "R2"),
        Vulnerability("V3", "T3", "D3", Severity.CRITICAL, ScanType.CODE_SECURITY, "L3", "R3"),
    ]
    assert result.critical_count == 2
    assert result.high_count == 1
    assert len(result.get_by_severity(Severity.CRITICAL)) == 2
    print("✓ 扫描结果属性测试通过")


def test_security_scanner_all():
    """测试安全扫描器主类"""
    scanner = SecurityScanner()
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = Path(tmpdir) / "test.py"
        code_file.write_text('password = "secret"\n')

        config_file = Path(tmpdir) / "config.json"
        config_file.write_text('{"port": 8080}')

        dep_file = Path(tmpdir) / "requirements.txt"
        dep_file.write_text("django<4.2.7\n")

        results = scanner.scan_all(str(tmpdir), str(config_file), str(dep_file))

    assert ScanType.DEPENDENCY in results
    assert ScanType.CODE_SECURITY in results
    assert ScanType.CONFIG_SECURITY in results
    assert ScanType.SECRET_LEAK in results

    summary = scanner.get_summary()
    assert summary["total_scans"] == 4
    assert summary["total_vulnerabilities"] > 0

    plan = scanner.get_remediation_plan()
    assert len(plan) > 0
    assert plan[0]["priority"] <= plan[-1]["priority"]
    print("✓ 安全扫描器主类测试通过")


def test_add_custom_rule():
    """测试添加自定义规则"""
    scanner = CodeSecurityScanner()
    scanner.add_rule({
        "id": "CUSTOM001",
        "name": "自定义规则",
        "pattern": r"eval\s*\(",
        "severity": Severity.HIGH,
        "description": "检测到eval调用",
        "remediation": "避免使用eval",
    })
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('eval("1+1")\n')
        temp_path = f.name

    result = scanner.scan(temp_path)
    Path(temp_path).unlink()
    ids = [v.id for v in result.vulnerabilities]
    assert "CUSTOM001" in ids
    print("✓ 添加自定义规则测试通过")


def test_add_custom_secret_pattern():
    """测试添加自定义密钥模式"""
    scanner = SecretLeakScanner()
    scanner.add_pattern({
        "id": "CUSTOM_SECRET",
        "name": "自定义密钥",
        "pattern": r"custom_secret_\w{10,}",
        "severity": Severity.HIGH,
        "description": "检测到自定义密钥",
        "remediation": "移除自定义密钥",
    })
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('custom_secret_abcdefghij\n')
        temp_path = f.name

    result = scanner.scan(temp_path)
    Path(temp_path).unlink()
    ids = [v.id for v in result.vulnerabilities]
    assert "CUSTOM_SECRET" in ids
    print("✓ 添加自定义密钥模式测试通过")


def main():
    print("=" * 60)
    print("阶段86验证：安全扫描器模块")
    print("=" * 60)

    test_dependency_scan()
    test_dependency_parse_file()
    test_code_security_scan()
    test_config_security_scan()
    test_secret_leak_scan()
    test_scan_result_properties()
    test_security_scanner_all()
    test_add_custom_rule()
    test_add_custom_secret_pattern()

    print("=" * 60)
    print("阶段86验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
