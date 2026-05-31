"""
安全扫描器模块
职责：依赖漏洞扫描、代码安全扫描、配置安全检查、密钥泄露检测
依赖规则：引用公共层 utils
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import re
import json

from common.utils import setup_logger

logger = setup_logger(__name__)


class Severity(Enum):
    """漏洞严重级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanType(Enum):
    """扫描类型"""
    DEPENDENCY = "dependency"
    CODE_SECURITY = "code_security"
    CONFIG_SECURITY = "config_security"
    SECRET_LEAK = "secret_leak"


@dataclass
class Vulnerability:
    """漏洞信息"""
    id: str
    title: str
    description: str
    severity: Severity
    scan_type: ScanType
    location: str
    remediation: str
    references: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """扫描结果"""
    scan_type: ScanType
    target: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    scanned_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return len(self.vulnerabilities) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    def get_by_severity(self, severity: Severity) -> List[Vulnerability]:
        return [v for v in self.vulnerabilities if v.severity == severity]


class BaseScanner(ABC):
    """扫描器基类"""

    def __init__(self, scan_type: ScanType):
        self.scan_type = scan_type
        self.logger = setup_logger(f"{__name__}.{scan_type.value}")

    @abstractmethod
    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行扫描"""
        pass

    def _create_result(self, target: str) -> ScanResult:
        return ScanResult(scan_type=self.scan_type, target=target)


class DependencyScanner(BaseScanner):
    """
    依赖漏洞扫描器
    检测已知漏洞依赖、过期依赖、可疑依赖
    """

    def __init__(self):
        super().__init__(ScanType.DEPENDENCY)
        self._vulnerability_db: Dict[str, List[Dict[str, Any]]] = {}
        self._init_mock_db()

    def _init_mock_db(self) -> None:
        """初始化模拟漏洞数据库"""
        self._vulnerability_db = {
            "requests": [
                {
                    "id": "CVE-2023-1234",
                    "title": "Requests库SSRF漏洞",
                    "description": "特定版本存在服务器端请求伪造漏洞",
                    "severity": Severity.HIGH,
                    "affected_versions": ["<2.31.0"],
                    "remediation": "升级到 requests >= 2.31.0",
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-1234"]
                }
            ],
            "django": [
                {
                    "id": "CVE-2023-5678",
                    "title": "Django SQL注入漏洞",
                    "description": "QuerySet存在SQL注入风险",
                    "severity": Severity.CRITICAL,
                    "affected_versions": ["<4.2.7"],
                    "remediation": "升级到 Django >= 4.2.7",
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-5678"]
                }
            ],
            "flask": [
                {
                    "id": "CVE-2023-9012",
                    "title": "Flask会话伪造漏洞",
                    "description": "会话管理存在伪造风险",
                    "severity": Severity.MEDIUM,
                    "affected_versions": ["<2.3.0"],
                    "remediation": "升级到 Flask >= 2.3.0",
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-9012"]
                }
            ]
        }

    def scan(self, target: str, **kwargs) -> ScanResult:
        """
        扫描依赖文件
        target: requirements.txt 路径或依赖名称
        """
        start = datetime.now()
        result = self._create_result(target)
        dependencies = self._parse_dependencies(target)

        for dep_name, dep_version in dependencies:
            vulns = self._check_dependency(dep_name, dep_version)
            for vuln_data in vulns:
                vuln = Vulnerability(
                    id=vuln_data["id"],
                    title=vuln_data["title"],
                    description=vuln_data["description"],
                    severity=vuln_data["severity"],
                    scan_type=self.scan_type,
                    location=f"{dep_name}=={dep_version}",
                    remediation=vuln_data["remediation"],
                    references=vuln_data["references"]
                )
                result.vulnerabilities.append(vuln)
                self.logger.warning(f"发现依赖漏洞: {vuln.id} - {vuln.title}")

        result.duration_ms = (datetime.now() - start).total_seconds() * 1000
        self.logger.info(f"依赖扫描完成: {target}, 发现 {len(result.vulnerabilities)} 个漏洞")
        return result

    def _parse_dependencies(self, target: str) -> List[tuple]:
        """解析依赖列表"""
        dependencies = []
        path = Path(target)

        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        dep = self._parse_requirement(line)
                        if dep:
                            dependencies.append(dep)
            except Exception as e:
                self.logger.error(f"读取依赖文件失败: {e}")
        else:
            for line in target.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                dep = self._parse_requirement(line)
                if dep:
                    dependencies.append(dep)

        return dependencies

    def _parse_requirement(self, line: str) -> Optional[tuple]:
        """解析单个依赖"""
        match = re.match(r"^([a-zA-Z0-9_-]+)([<>=!~].+)?", line)
        if match:
            name = match.group(1).lower()
            version = match.group(2) or "unknown"
            version = version.lstrip("<>=!~")
            return name, version
        return None

    def _check_dependency(self, name: str, version: str) -> List[Dict[str, Any]]:
        """检查依赖漏洞"""
        results = []
        known_vulns = self._vulnerability_db.get(name, [])
        for vuln in known_vulns:
            results.append(vuln)
        return results

    def register_vulnerability(self, package: str, vuln_data: Dict[str, Any]) -> None:
        """注册漏洞信息"""
        if package not in self._vulnerability_db:
            self._vulnerability_db[package] = []
        self._vulnerability_db[package].append(vuln_data)
        self.logger.info(f"注册漏洞: {vuln_data.get('id')} -> {package}")


class CodeSecurityScanner(BaseScanner):
    """
    代码安全扫描器
    检测SQL注入、XSS、命令注入、不安全的反序列化等
    """

    def __init__(self):
        super().__init__(ScanType.CODE_SECURITY)
        self._rules: List[Dict[str, Any]] = []
        self._init_rules()

    def _init_rules(self) -> None:
        """初始化安全规则"""
        self._rules = [
            {
                "id": "SEC001",
                "name": "SQL注入风险",
                "pattern": r"(execute|query)\s*\(\s*['\"].*%s.*['\"]",
                "severity": Severity.CRITICAL,
                "description": "检测到可能的SQL注入漏洞：字符串拼接SQL语句",
                "remediation": "使用参数化查询或ORM",
            },
            {
                "id": "SEC002",
                "name": "命令注入风险",
                "pattern": r"(os\.system|subprocess\.call|subprocess\.run)\s*\(.*\+.*\)",
                "severity": Severity.CRITICAL,
                "description": "检测到可能的命令注入漏洞：动态拼接命令",
                "remediation": "使用参数列表传递命令，避免shell=True",
            },
            {
                "id": "SEC003",
                "name": "不安全的反序列化",
                "pattern": r"pickle\.loads?\s*\(",
                "severity": Severity.HIGH,
                "description": "使用pickle反序列化不可信数据存在安全风险",
                "remediation": "使用JSON等安全格式替代pickle",
            },
            {
                "id": "SEC004",
                "name": "硬编码密码",
                "pattern": r"(password|passwd|pwd)\s*=\s*['\"][^'\"]+['\"]",
                "severity": Severity.HIGH,
                "description": "检测到可能的硬编码密码",
                "remediation": "使用环境变量或密钥管理服务",
            },
            {
                "id": "SEC005",
                "name": "不安全的哈希",
                "pattern": r"hashlib\.md5\s*\(",
                "severity": Severity.MEDIUM,
                "description": "MD5已被证明不安全，应避免用于安全场景",
                "remediation": "使用SHA-256或更安全的哈希算法",
            },
            {
                "id": "SEC006",
                "name": "调试模式开启",
                "pattern": r"debug\s*=\s*True",
                "severity": Severity.MEDIUM,
                "description": "生产环境不应开启调试模式",
                "remediation": "生产环境设置 debug = False",
            },
        ]

    def scan(self, target: str, **kwargs) -> ScanResult:
        """
        扫描代码文件或目录
        target: 文件或目录路径
        """
        start = datetime.now()
        result = self._create_result(target)
        path = Path(target)

        if path.is_file():
            self._scan_file(path, result)
        elif path.is_dir():
            for file_path in path.rglob("*.py"):
                self._scan_file(file_path, result)

        result.duration_ms = (datetime.now() - start).total_seconds() * 1000
        self.logger.info(f"代码安全扫描完成: {target}, 发现 {len(result.vulnerabilities)} 个问题")
        return result

    def _scan_file(self, file_path: Path, result: ScanResult) -> None:
        """扫描单个文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            for rule in self._rules:
                for line_num, line in enumerate(lines, 1):
                    if re.search(rule["pattern"], line):
                        vuln = Vulnerability(
                            id=rule["id"],
                            title=rule["name"],
                            description=rule["description"],
                            severity=rule["severity"],
                            scan_type=self.scan_type,
                            location=f"{file_path}:{line_num}",
                            remediation=rule["remediation"]
                        )
                        result.vulnerabilities.append(vuln)
                        self.logger.warning(f"发现代码安全问题: {vuln.id} at {vuln.location}")
        except Exception as e:
            self.logger.error(f"扫描文件失败 {file_path}: {e}")

    def add_rule(self, rule: Dict[str, Any]) -> None:
        """添加自定义规则"""
        self._rules.append(rule)
        self.logger.info(f"添加安全规则: {rule.get('id')}")


class ConfigSecurityScanner(BaseScanner):
    """
    配置安全检查器
    检测弱密码策略、不安全的端口、敏感配置暴露等
    """

    def __init__(self):
        super().__init__(ScanType.CONFIG_SECURITY)
        self._checks: List[Dict[str, Any]] = []
        self._init_checks()

    def _init_checks(self) -> None:
        """初始化配置检查项"""
        self._checks = [
            {
                "id": "CFG001",
                "name": "弱密码策略",
                "check": self._check_password_policy,
                "severity": Severity.HIGH,
                "description": "密码策略过于宽松",
                "remediation": "设置最小密码长度为12，要求复杂度",
            },
            {
                "id": "CFG002",
                "name": "不安全的端口",
                "check": self._check_insecure_ports,
                "severity": Severity.MEDIUM,
                "description": "服务运行在不安全的默认端口",
                "remediation": "修改默认端口，使用非标准端口",
            },
            {
                "id": "CFG003",
                "name": "CSRF保护关闭",
                "check": self._check_csrf_protection,
                "severity": Severity.HIGH,
                "description": "CSRF保护未启用",
                "remediation": "启用CSRF保护机制",
            },
            {
                "id": "CFG004",
                "name": "CORS配置过于宽松",
                "check": self._check_cors_policy,
                "severity": Severity.MEDIUM,
                "description": "CORS允许所有来源访问",
                "remediation": "限制CORS允许的来源域名",
            },
        ]

    def scan(self, target: str, **kwargs) -> ScanResult:
        """
        扫描配置文件
        target: 配置文件路径或配置字典
        """
        start = datetime.now()
        result = self._create_result(target)
        config = self._load_config(target)

        for check in self._checks:
            issues = check["check"](config)
            for issue in issues:
                vuln = Vulnerability(
                    id=check["id"],
                    title=check["name"],
                    description=check["description"] + ": " + issue,
                    severity=check["severity"],
                    scan_type=self.scan_type,
                    location=target,
                    remediation=check["remediation"]
                )
                result.vulnerabilities.append(vuln)
                self.logger.warning(f"发现配置安全问题: {vuln.id} - {issue}")

        result.duration_ms = (datetime.now() - start).total_seconds() * 1000
        self.logger.info(f"配置安全扫描完成: {target}, 发现 {len(result.vulnerabilities)} 个问题")
        return result

    def _load_config(self, target: str) -> Dict[str, Any]:
        """加载配置"""
        path = Path(target)
        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if path.suffix == ".json":
                        return json.load(f)
                    else:
                        return {"raw": f.read()}
            except Exception as e:
                self.logger.error(f"加载配置失败: {e}")
        if not path.exists():
            try:
                return json.loads(target)
            except Exception:
                pass
        return {}

    def _check_password_policy(self, config: Dict[str, Any]) -> List[str]:
        """检查密码策略"""
        issues = []
        password_config = config.get("password_policy", {})
        min_length = password_config.get("min_length", 0)
        if min_length < 12:
            issues.append(f"最小密码长度仅为 {min_length}")
        if not password_config.get("require_complexity", False):
            issues.append("未要求密码复杂度")
        return issues

    def _check_insecure_ports(self, config: Dict[str, Any]) -> List[str]:
        """检查不安全端口"""
        issues = []
        port = config.get("port", 0)
        insecure_ports = {21, 23, 80, 110, 143, 3306, 5432, 6379, 8080, 9200}
        if port in insecure_ports:
            issues.append(f"服务运行在默认端口 {port}")
        return issues

    def _check_csrf_protection(self, config: Dict[str, Any]) -> List[str]:
        """检查CSRF保护"""
        issues = []
        if config.get("csrf_enabled", True) is False:
            issues.append("CSRF保护已显式关闭")
        return issues

    def _check_cors_policy(self, config: Dict[str, Any]) -> List[str]:
        """检查CORS策略"""
        issues = []
        cors = config.get("cors", {})
        if cors.get("allow_all", False):
            issues.append("CORS允许所有来源")
        allowed = cors.get("allowed_origins", [])
        if "*" in allowed:
            issues.append("CORS允许来源包含通配符 *")
        return issues


class SecretLeakScanner(BaseScanner):
    """
    密钥泄露检测器
    检测API密钥、密码、Token、私钥等敏感信息泄露
    """

    def __init__(self):
        super().__init__(ScanType.SECRET_LEAK)
        self._patterns: List[Dict[str, Any]] = []
        self._init_patterns()

    def _init_patterns(self) -> None:
        """初始化检测模式"""
        self._patterns = [
            {
                "id": "LEAK001",
                "name": "AWS访问密钥",
                "pattern": r"AKIA[0-9A-Z]{16}",
                "severity": Severity.CRITICAL,
                "description": "检测到AWS访问密钥",
                "remediation": "立即轮换密钥，使用环境变量或密钥管理服务",
            },
            {
                "id": "LEAK002",
                "name": "GitHub Token",
                "pattern": r"ghp_[a-zA-Z0-9]{36}",
                "severity": Severity.CRITICAL,
                "description": "检测到GitHub个人访问令牌",
                "remediation": "立即撤销并重新生成Token",
            },
            {
                "id": "LEAK003",
                "name": "私钥文件",
                "pattern": r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
                "severity": Severity.CRITICAL,
                "description": "检测到私钥内容",
                "remediation": "从代码仓库中移除私钥，使用密钥管理服务",
            },
            {
                "id": "LEAK004",
                "name": "数据库连接字符串密码",
                "pattern": r"(mysql|postgresql|mongodb)://[^:]+:([^@]+)@",
                "severity": Severity.HIGH,
                "description": "检测到数据库连接字符串中包含密码",
                "remediation": "使用连接字符串配置文件或密钥管理服务",
            },
            {
                "id": "LEAK005",
                "name": "API密钥",
                "pattern": r"api[_-]?key\s*[:=]\s*['\"][a-zA-Z0-9]{16,}['\"]",
                "severity": Severity.HIGH,
                "description": "检测到硬编码API密钥",
                "remediation": "使用环境变量存储API密钥",
            },
            {
                "id": "LEAK006",
                "name": "JWT Token",
                "pattern": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
                "severity": Severity.HIGH,
                "description": "检测到JWT Token",
                "remediation": "从代码中移除JWT Token",
            },
        ]

    def scan(self, target: str, **kwargs) -> ScanResult:
        """
        扫描密钥泄露
        target: 文件或目录路径
        """
        start = datetime.now()
        result = self._create_result(target)
        path = Path(target)

        if path.is_file():
            self._scan_file_for_secrets(path, result)
        elif path.is_dir():
            for file_path in path.rglob("*"):
                if file_path.is_file() and not self._is_binary(file_path):
                    self._scan_file_for_secrets(file_path, result)

        result.duration_ms = (datetime.now() - start).total_seconds() * 1000
        self.logger.info(f"密钥泄露扫描完成: {target}, 发现 {len(result.vulnerabilities)} 个泄露")
        return result

    def _scan_file_for_secrets(self, file_path: Path, result: ScanResult) -> None:
        """扫描文件中的密钥泄露"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.split("\n")

            for pattern in self._patterns:
                for line_num, line in enumerate(lines, 1):
                    if re.search(pattern["pattern"], line, re.IGNORECASE):
                        vuln = Vulnerability(
                            id=pattern["id"],
                            title=pattern["name"],
                            description=pattern["description"],
                            severity=pattern["severity"],
                            scan_type=self.scan_type,
                            location=f"{file_path}:{line_num}",
                            remediation=pattern["remediation"]
                        )
                        result.vulnerabilities.append(vuln)
                        self.logger.warning(f"发现密钥泄露: {vuln.id} at {vuln.location}")
        except Exception as e:
            self.logger.error(f"扫描文件失败 {file_path}: {e}")

    def _is_binary(self, file_path: Path) -> bool:
        """检查是否为二进制文件"""
        binary_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz"}
        return file_path.suffix.lower() in binary_extensions

    def add_pattern(self, pattern: Dict[str, Any]) -> None:
        """添加自定义检测模式"""
        self._patterns.append(pattern)
        self.logger.info(f"添加密钥检测模式: {pattern.get('id')}")


class SecurityScanner:
    """
    安全扫描器主类
    整合所有扫描功能
    """

    def __init__(self):
        self.dependency_scanner = DependencyScanner()
        self.code_scanner = CodeSecurityScanner()
        self.config_scanner = ConfigSecurityScanner()
        self.secret_scanner = SecretLeakScanner()
        self.logger = setup_logger(__name__)
        self._scan_history: List[ScanResult] = []

    def scan_all(self, code_path: str, config_path: str, dependency_path: str) -> Dict[ScanType, ScanResult]:
        """
        执行全量安全扫描
        """
        self.logger.info("开始全量安全扫描")
        results = {}

        results[ScanType.CODE_SECURITY] = self.code_scanner.scan(code_path)
        results[ScanType.CONFIG_SECURITY] = self.config_scanner.scan(config_path)
        results[ScanType.DEPENDENCY] = self.dependency_scanner.scan(dependency_path)
        results[ScanType.SECRET_LEAK] = self.secret_scanner.scan(code_path)

        for result in results.values():
            self._scan_history.append(result)

        total_vulns = sum(len(r.vulnerabilities) for r in results.values())
        self.logger.info(f"全量扫描完成，共发现 {total_vulns} 个安全问题")
        return results

    def get_summary(self) -> Dict[str, Any]:
        """获取扫描汇总"""
        summary = {
            "total_scans": len(self._scan_history),
            "total_vulnerabilities": 0,
            "by_severity": {
                Severity.CRITICAL.value: 0,
                Severity.HIGH.value: 0,
                Severity.MEDIUM.value: 0,
                Severity.LOW.value: 0,
                Severity.INFO.value: 0,
            },
            "by_type": {
                ScanType.DEPENDENCY.value: 0,
                ScanType.CODE_SECURITY.value: 0,
                ScanType.CONFIG_SECURITY.value: 0,
                ScanType.SECRET_LEAK.value: 0,
            }
        }

        for result in self._scan_history:
            summary["total_vulnerabilities"] += len(result.vulnerabilities)
            summary["by_type"][result.scan_type.value] += len(result.vulnerabilities)
            for vuln in result.vulnerabilities:
                summary["by_severity"][vuln.severity.value] += 1

        return summary

    def get_remediation_plan(self) -> List[Dict[str, Any]]:
        """生成修复计划"""
        plan = []
        for result in self._scan_history:
            for vuln in result.vulnerabilities:
                plan.append({
                    "id": vuln.id,
                    "title": vuln.title,
                    "severity": vuln.severity.value,
                    "location": vuln.location,
                    "remediation": vuln.remediation,
                    "priority": self._calculate_priority(vuln.severity)
                })

        plan.sort(key=lambda x: x["priority"])
        return plan

    def _calculate_priority(self, severity: Severity) -> int:
        """计算修复优先级"""
        priorities = {
            Severity.CRITICAL: 1,
            Severity.HIGH: 2,
            Severity.MEDIUM: 3,
            Severity.LOW: 4,
            Severity.INFO: 5
        }
        return priorities.get(severity, 99)


def demo_security_scanner():
    """演示安全扫描器"""
    print("=" * 70)
    print("安全扫描器系统演示")
    print("=" * 70)
    print()

    scanner = SecurityScanner()

    print("1. 依赖漏洞扫描:")
    dep_result = scanner.dependency_scanner.scan("django<4.2.7\nrequests<2.31.0")
    print(f"   扫描目标: django<4.2.7, requests<2.31.0")
    print(f"   发现漏洞: {len(dep_result.vulnerabilities)} 个")
    for vuln in dep_result.vulnerabilities:
        print(f"   - [{vuln.severity.value}] {vuln.id}: {vuln.title}")
    print()

    print("2. 代码安全扫描:")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('import os\n')
        f.write('os.system("ls " + user_input)\n')
        f.write('password = "secret123"\n')
        f.write('debug = True\n')
        temp_path = f.name

    code_result = scanner.code_scanner.scan(temp_path)
    print(f"   扫描目标: {temp_path}")
    print(f"   发现问题: {len(code_result.vulnerabilities)} 个")
    for vuln in code_result.vulnerabilities:
        print(f"   - [{vuln.severity.value}] {vuln.id}: {vuln.title}")
    Path(temp_path).unlink()
    print()

    print("3. 配置安全扫描:")
    config_result = scanner.config_scanner.scan("{}")
    print(f"   发现问题: {len(config_result.vulnerabilities)} 个")
    print()

    print("4. 密钥泄露扫描:")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('api_key = "sk-1234567890abcdef"\n')
        f.write('aws_key = "AKIAIOSFODNN7EXAMPLE"\n')
        temp_path = f.name

    secret_result = scanner.secret_scanner.scan(temp_path)
    print(f"   扫描目标: {temp_path}")
    print(f"   发现泄露: {len(secret_result.vulnerabilities)} 个")
    for vuln in secret_result.vulnerabilities:
        print(f"   - [{vuln.severity.value}] {vuln.id}: {vuln.title}")
    Path(temp_path).unlink()
    print()

    print("5. 扫描汇总:")
    summary = scanner.get_summary()
    print(f"   总扫描次数: {summary['total_scans']}")
    print(f"   总漏洞数: {summary['total_vulnerabilities']}")
    print(f"   按严重级别: {summary['by_severity']}")
    print()

    print("=" * 70)
    print("安全扫描器系统演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_security_scanner()
