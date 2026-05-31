"""
隐私保护模块
职责：PII识别、数据匿名化、同意管理、数据主体权利
依赖规则：引用公共层 utils
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Callable
import re
import hashlib
import uuid

from common.utils import setup_logger

logger = setup_logger(__name__)


class PIIType(Enum):
    """PII类型"""
    EMAIL = "email"
    PHONE = "phone"
    ID_CARD = "id_card"
    NAME = "name"
    ADDRESS = "address"
    BANK_CARD = "bank_card"
    IP_ADDRESS = "ip_address"
    LOCATION = "location"
    DATE_OF_BIRTH = "date_of_birth"


class ConsentStatus(Enum):
    """同意状态"""
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    REVOKED = "revoked"
    EXPIRED = "expired"


class DataSubjectRight(Enum):
    """数据主体权利"""
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    RESTRICTION = "restriction"
    PORTABILITY = "portability"
    OBJECTION = "objection"


@dataclass
class PIIFinding:
    """PII发现记录"""
    pii_type: PIIType
    value: str
    location: str
    confidence: float
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class ConsentRecord:
    """同意记录"""
    subject_id: str
    purpose: str
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        if self.status != ConsentStatus.GRANTED:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


@dataclass
class DataSubjectRequest:
    """数据主体请求"""
    request_id: str
    subject_id: str
    right: DataSubjectRight
    requested_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None


class PIIRecognizer(ABC):
    """PII识别器基类"""

    @abstractmethod
    def recognize(self, text: str) -> List[PIIFinding]:
        pass


class RegexPIIRecognizer(PIIRecognizer):
    """基于正则的PII识别器"""

    def __init__(self):
        self._patterns: Dict[PIIType, re.Pattern] = {}
        self._init_patterns()

    def _init_patterns(self) -> None:
        self._patterns[PIIType.EMAIL] = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )
        self._patterns[PIIType.PHONE] = re.compile(
            r"\b(?:\+?86)?1[3-9]\d{9}\b|\b\d{3}-\d{8}\b|\b\d{4}-\d{7}\b"
        )
        self._patterns[PIIType.ID_CARD] = re.compile(
            r"\b\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
        )
        self._patterns[PIIType.IP_ADDRESS] = re.compile(
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        )
        self._patterns[PIIType.BANK_CARD] = re.compile(
            r"\b(?:4\d{15}|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b"
        )

    def recognize(self, text: str) -> List[PIIFinding]:
        findings = []
        for pii_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                findings.append(PIIFinding(
                    pii_type=pii_type,
                    value=match.group(),
                    location="text",
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        return findings


class Anonymizer(ABC):
    """匿名化器基类"""

    @abstractmethod
    def anonymize(self, value: str, pii_type: PIIType) -> str:
        pass


class HashAnonymizer(Anonymizer):
    """哈希匿名化器"""

    def __init__(self, salt: Optional[str] = None):
        self.salt = salt or str(uuid.uuid4())

    def anonymize(self, value: str, pii_type: PIIType) -> str:
        salted = f"{value}:{self.salt}"
        hashed = hashlib.sha256(salted.encode()).hexdigest()[:16]
        return f"{pii_type.value}_{hashed}"


class MaskAnonymizer(Anonymizer):
    """掩码匿名化器"""

    def anonymize(self, value: str, pii_type: PIIType) -> str:
        if len(value) <= 4:
            return "****"
        return value[:2] + "****" + value[-2:]


class GeneralizationAnonymizer(Anonymizer):
    """泛化匿名化器"""

    def anonymize(self, value: str, pii_type: PIIType) -> str:
        if pii_type == PIIType.EMAIL:
            parts = value.split("@")
            return parts[0][:2] + "***@" + parts[1]
        elif pii_type == PIIType.PHONE:
            return value[:3] + "****" + value[-4:]
        elif pii_type == PIIType.ID_CARD:
            return value[:6] + "********" + value[-4:]
        return "***"


class DataAnonymizer:
    """
    数据匿名化器
    支持多种匿名化策略
    """

    def __init__(self):
        self._strategies: Dict[str, Anonymizer] = {
            "hash": HashAnonymizer(),
            "mask": MaskAnonymizer(),
            "generalize": GeneralizationAnonymizer(),
        }
        self._recognizer = RegexPIIRecognizer()
        self.logger = setup_logger(f"{__name__}.anonymizer")

    def anonymize_text(self, text: str, strategy: str = "generalize") -> str:
        """匿名化文本中的PII"""
        anonymizer = self._strategies.get(strategy, self._strategies["generalize"])
        findings = self._recognizer.recognize(text)

        result = text
        for finding in sorted(findings, key=lambda x: x.start_pos, reverse=True):
            replacement = anonymizer.anonymize(finding.value, finding.pii_type)
            result = result[:finding.start_pos] + replacement + result[finding.end_pos:]

        self.logger.info(f"匿名化完成: 发现 {len(findings)} 处PII，策略={strategy}")
        return result

    def anonymize_dict(self, data: Dict[str, Any], strategy: str = "generalize",
                       sensitive_keys: Optional[Set[str]] = None) -> Dict[str, Any]:
        """匿名化字典中的敏感字段"""
        sensitive_keys = sensitive_keys or {"email", "phone", "name", "address", "password"}
        result = {}
        anonymizer = self._strategies.get(strategy, self._strategies["generalize"])

        for key, value in data.items():
            if key.lower() in sensitive_keys and isinstance(value, str):
                pii_type = self._infer_pii_type(value)
                result[key] = anonymizer.anonymize(value, pii_type)
            elif isinstance(value, dict):
                result[key] = self.anonymize_dict(value, strategy, sensitive_keys)
            else:
                result[key] = value

        return result

    def _infer_pii_type(self, value: str) -> PIIType:
        """推断PII类型"""
        findings = self._recognizer.recognize(value)
        if findings:
            return findings[0].pii_type
        return PIIType.NAME

    def register_strategy(self, name: str, anonymizer: Anonymizer) -> None:
        """注册匿名化策略"""
        self._strategies[name] = anonymizer
        self.logger.info(f"注册匿名化策略: {name}")


class ConsentManager:
    """
    同意管理器
    管理用户同意记录
    """

    def __init__(self):
        self._records: Dict[str, List[ConsentRecord]] = {}
        self.logger = setup_logger(f"{__name__}.consent")

    def grant_consent(self, subject_id: str, purpose: str,
                      expires_at: Optional[datetime] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> ConsentRecord:
        """授予同意"""
        record = ConsentRecord(
            subject_id=subject_id,
            purpose=purpose,
            status=ConsentStatus.GRANTED,
            granted_at=datetime.now(),
            expires_at=expires_at,
            metadata=metadata or {}
        )

        if subject_id not in self._records:
            self._records[subject_id] = []
        self._records[subject_id].append(record)

        self.logger.info(f"同意授予: subject={subject_id}, purpose={purpose}")
        return record

    def revoke_consent(self, subject_id: str, purpose: str) -> bool:
        """撤销同意"""
        records = self._records.get(subject_id, [])
        revoked = False
        for record in records:
            if record.purpose == purpose and record.status == ConsentStatus.GRANTED:
                record.status = ConsentStatus.REVOKED
                revoked = True
                self.logger.info(f"同意撤销: subject={subject_id}, purpose={purpose}")
        return revoked

    def check_consent(self, subject_id: str, purpose: str) -> bool:
        """检查同意是否有效"""
        records = self._records.get(subject_id, [])
        for record in records:
            if record.purpose == purpose and record.is_valid():
                return True
        return False

    def get_consent_history(self, subject_id: str) -> List[ConsentRecord]:
        """获取同意历史"""
        return self._records.get(subject_id, [])

    def get_all_purposes(self, subject_id: str) -> Dict[str, ConsentStatus]:
        """获取所有目的的最新同意状态"""
        records = self._records.get(subject_id, [])
        purposes = {}
        for record in records:
            purposes[record.purpose] = record.status
        return purposes


class DataSubjectRightsManager:
    """
    数据主体权利管理器
    处理访问、更正、删除、可携带等请求
    """

    def __init__(self):
        self._requests: Dict[str, DataSubjectRequest] = {}
        self._data_store: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[DataSubjectRight, Callable] = {}
        self.logger = setup_logger(f"{__name__}.rights")
        self._init_default_handlers()

    def _init_default_handlers(self) -> None:
        """初始化默认处理器"""
        self._handlers[DataSubjectRight.ACCESS] = self._handle_access
        self._handlers[DataSubjectRight.ERASURE] = self._handle_erasure
        self._handlers[DataSubjectRight.RECTIFICATION] = self._handle_rectification
        self._handlers[DataSubjectRight.PORTABILITY] = self._handle_portability

    def register_data(self, subject_id: str, data: Dict[str, Any]) -> None:
        """注册主体数据"""
        self._data_store[subject_id] = data
        self.logger.info(f"注册数据: subject={subject_id}")

    def submit_request(self, subject_id: str, right: DataSubjectRight) -> str:
        """提交权利请求"""
        request_id = str(uuid.uuid4())
        request = DataSubjectRequest(
            request_id=request_id,
            subject_id=subject_id,
            right=right
        )
        self._requests[request_id] = request
        self.logger.info(f"提交请求: {request_id}, right={right.value}, subject={subject_id}")
        return request_id

    def process_request(self, request_id: str, **kwargs) -> DataSubjectRequest:
        """处理请求"""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"请求不存在: {request_id}")

        handler = self._handlers.get(request.right)
        if handler:
            result = handler(request.subject_id, **kwargs)
            request.result = result
            request.status = "completed"
            self.logger.info(f"请求处理完成: {request_id}")
        else:
            request.status = "failed"
            request.result = {"error": "无可用处理器"}

        return request

    def get_request_status(self, request_id: str) -> Optional[DataSubjectRequest]:
        """获取请求状态"""
        return self._requests.get(request_id)

    def _handle_access(self, subject_id: str, **kwargs) -> Dict[str, Any]:
        """处理访问请求"""
        data = self._data_store.get(subject_id, {})
        return {
            "subject_id": subject_id,
            "data": data,
            "fields_count": len(data)
        }

    def _handle_erasure(self, subject_id: str, **kwargs) -> Dict[str, Any]:
        """处理删除请求"""
        if subject_id in self._data_store:
            del self._data_store[subject_id]
            return {"subject_id": subject_id, "erased": True}
        return {"subject_id": subject_id, "erased": False, "reason": "数据不存在"}

    def _handle_rectification(self, subject_id: str, updates: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """处理更正请求"""
        if subject_id not in self._data_store:
            return {"subject_id": subject_id, "updated": False, "reason": "数据不存在"}
        self._data_store[subject_id].update(updates)
        return {"subject_id": subject_id, "updated": True, "fields": list(updates.keys())}

    def _handle_portability(self, subject_id: str, **kwargs) -> Dict[str, Any]:
        """处理可携带请求"""
        data = self._data_store.get(subject_id, {})
        return {
            "subject_id": subject_id,
            "format": "json",
            "data": data,
            "export_timestamp": datetime.now().isoformat()
        }

    def register_handler(self, right: DataSubjectRight, handler: Callable) -> None:
        """注册自定义处理器"""
        self._handlers[right] = handler
        self.logger.info(f"注册处理器: {right.value}")


class PrivacyProtection:
    """
    隐私保护主类
    整合PII识别、匿名化、同意管理、权利管理
    """

    def __init__(self):
        self.pii_recognizer = RegexPIIRecognizer()
        self.anonymizer = DataAnonymizer()
        self.consent_manager = ConsentManager()
        self.rights_manager = DataSubjectRightsManager()
        self.logger = setup_logger(__name__)

    def scan_pii(self, text: str) -> List[PIIFinding]:
        """扫描文本中的PII"""
        return self.pii_recognizer.recognize(text)

    def anonymize(self, data: Any, strategy: str = "generalize") -> Any:
        """匿名化数据"""
        if isinstance(data, str):
            return self.anonymizer.anonymize_text(data, strategy)
        elif isinstance(data, dict):
            return self.anonymizer.anonymize_dict(data, strategy)
        return data

    def check_processing_allowed(self, subject_id: str, purpose: str) -> bool:
        """检查是否允许处理数据"""
        return self.consent_manager.check_consent(subject_id, purpose)

    def handle_data_request(self, subject_id: str, right: DataSubjectRight, **kwargs) -> DataSubjectRequest:
        """处理数据主体请求"""
        request_id = self.rights_manager.submit_request(subject_id, right)
        return self.rights_manager.process_request(request_id, **kwargs)

    def get_privacy_report(self, subject_id: str) -> Dict[str, Any]:
        """获取隐私报告"""
        return {
            "subject_id": subject_id,
            "consents": {
                purpose: status.value
                for purpose, status in self.consent_manager.get_all_purposes(subject_id).items()
            },
            "data_registered": subject_id in self.rights_manager._data_store,
            "requests": [
                {
                    "request_id": req.request_id,
                    "right": req.right.value,
                    "status": req.status,
                    "requested_at": req.requested_at.isoformat()
                }
                for req in self.rights_manager._requests.values()
                if req.subject_id == subject_id
            ]
        }


def demo_privacy_protection():
    """演示隐私保护系统"""
    print("=" * 70)
    print("隐私保护系统演示")
    print("=" * 70)
    print()

    privacy = PrivacyProtection()

    print("1. PII识别:")
    text = "用户张三，邮箱 zhangsan@example.com，手机 13800138000，身份证 110101199001011234"
    findings = privacy.scan_pii(text)
    print(f"   文本: {text}")
    print(f"   发现PII: {len(findings)} 处")
    for f in findings:
        print(f"   - {f.pii_type.value}: {f.value}")
    print()

    print("2. 数据匿名化:")
    anonymized = privacy.anonymize(text, strategy="generalize")
    print(f"   匿名化后: {anonymized}")
    print()

    print("3. 字典匿名化:")
    data = {
        "name": "李四",
        "email": "lisi@example.com",
        "phone": "13900139000",
        "age": 30
    }
    anonymized_dict = privacy.anonymize(data, strategy="mask")
    print(f"   原始: {data}")
    print(f"   匿名化后: {anonymized_dict}")
    print()

    print("4. 同意管理:")
    privacy.consent_manager.grant_consent("user_001", "marketing")
    privacy.consent_manager.grant_consent("user_001", "analytics")
    print(f"   marketing同意: {privacy.consent_manager.check_consent('user_001', 'marketing')}")
    privacy.consent_manager.revoke_consent("user_001", "marketing")
    print(f"   撤销后marketing同意: {privacy.consent_manager.check_consent('user_001', 'marketing')}")
    print(f"   analytics同意: {privacy.consent_manager.check_consent('user_001', 'analytics')}")
    print()

    print("5. 数据主体权利:")
    privacy.rights_manager.register_data("user_001", {
        "name": "王五",
        "email": "wangwu@example.com",
        "orders": ["order_1", "order_2"]
    })

    request = privacy.handle_data_request("user_001", DataSubjectRight.ACCESS)
    print(f"   访问请求结果: {request.result}")

    request = privacy.handle_data_request("user_001", DataSubjectRight.PORTABILITY)
    print(f"   可携带请求结果: 格式={request.result.get('format')}")

    request = privacy.handle_data_request("user_001", DataSubjectRight.RECTIFICATION, updates={"name": "王五（已更正）"})
    print(f"   更正请求结果: {request.result}")
    print()

    print("6. 隐私报告:")
    report = privacy.get_privacy_report("user_001")
    print(f"   {report}")
    print()

    print("=" * 70)
    print("隐私保护系统演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_privacy_protection()
