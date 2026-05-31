"""
数据脱敏模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 敏感数据识别
2. 数据脱敏
3. 部分掩码
4. 格式保留加密
"""

from __future__ import annotations

import hashlib
import random
import re
import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class SensitivityLevel(Enum):
    """敏感度级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaskType(Enum):
    """掩码类型"""
    FULL = "full"
    PARTIAL = "partial"
    HASH = "hash"
    FPE = "fpe"
    TRUNCATE = "truncate"


@dataclass
class SensitivePattern:
    """敏感数据模式"""
    name: str
    pattern: Pattern
    level: SensitivityLevel
    mask_type: MaskType
    description: str


class SensitiveDataRecognizer:
    """敏感数据识别器"""

    DEFAULT_PATTERNS = [
        SensitivePattern(
            name="phone",
            pattern=re.compile(r"1[3-9]\d{9}"),
            level=SensitivityLevel.MEDIUM,
            mask_type=MaskType.PARTIAL,
            description="手机号",
        ),
        SensitivePattern(
            name="id_card",
            pattern=re.compile(r"\d{17}[\dXx]|\d{15}"),
            level=SensitivityLevel.HIGH,
            mask_type=MaskType.PARTIAL,
            description="身份证号",
        ),
        SensitivePattern(
            name="email",
            pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            level=SensitivityLevel.MEDIUM,
            mask_type=MaskType.PARTIAL,
            description="邮箱地址",
        ),
        SensitivePattern(
            name="bank_card",
            pattern=re.compile(r"\d{16,19}"),
            level=SensitivityLevel.HIGH,
            mask_type=MaskType.PARTIAL,
            description="银行卡号",
        ),
        SensitivePattern(
            name="ip_address",
            pattern=re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
            level=SensitivityLevel.LOW,
            mask_type=MaskType.PARTIAL,
            description="IP地址",
        ),
        SensitivePattern(
            name="password",
            pattern=re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*[^\s&]+"),
            level=SensitivityLevel.CRITICAL,
            mask_type=MaskType.FULL,
            description="密码",
        ),
    ]

    def __init__(self, patterns: Optional[List[SensitivePattern]] = None):
        self.patterns = patterns or list(self.DEFAULT_PATTERNS)
        self.logger = setup_logger(__name__ + ".SensitiveDataRecognizer")

    def recognize(self, text: str) -> List[Dict[str, Any]]:
        """识别文本中的敏感数据"""
        findings = []
        for sp in self.patterns:
            for match in sp.pattern.finditer(text):
                findings.append({
                    "name": sp.name,
                    "level": sp.level.value,
                    "mask_type": sp.mask_type.value,
                    "description": sp.description,
                    "match": match.group(0),
                    "position": (match.start(), match.end()),
                })
        return findings

    def has_sensitive_data(self, text: str) -> bool:
        """判断文本是否包含敏感数据"""
        return len(self.recognize(text)) > 0

    def add_pattern(self, pattern: SensitivePattern):
        """添加自定义模式"""
        self.patterns.append(pattern)


class DataMasker:
    """数据脱敏器"""

    @staticmethod
    def mask_full(value: str, mask_char: str = "*") -> str:
        """完全掩码"""
        return mask_char * len(value)

    @staticmethod
    def mask_partial(value: str, visible_start: int = 2, visible_end: int = 2, mask_char: str = "*") -> str:
        """部分掩码"""
        if len(value) <= visible_start + visible_end:
            return mask_char * len(value)
        return value[:visible_start] + mask_char * (len(value) - visible_start - visible_end) + value[-visible_end:]

    @staticmethod
    def mask_hash(value: str, algorithm: str = "sha256") -> str:
        """哈希掩码"""
        h = hashlib.new(algorithm, value.encode("utf-8"))
        return h.hexdigest()[:16]

    @staticmethod
    def mask_truncate(value: str, keep: int = 4) -> str:
        """截断掩码"""
        if len(value) <= keep:
            return "*" * len(value)
        return value[:keep] + "..."

    @staticmethod
    def mask_phone(phone: str) -> str:
        """手机号掩码"""
        return DataMasker.mask_partial(phone, 3, 4)

    @staticmethod
    def mask_id_card(id_card: str) -> str:
        """身份证号掩码"""
        return DataMasker.mask_partial(id_card, 4, 4)

    @staticmethod
    def mask_email(email: str) -> str:
        """邮箱掩码"""
        parts = email.split("@")
        if len(parts) != 2:
            return "*" * len(email)
        local = parts[0]
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return f"{masked_local}@{parts[1]}"

    @staticmethod
    def mask_bank_card(card: str) -> str:
        """银行卡号掩码"""
        return DataMasker.mask_partial(card, 4, 4)


class FormatPreservingEncryption:
    """格式保留加密（FPE）- 简化实现"""

    def __init__(self, key: Optional[str] = None):
        self.key = key or "default_fpe_key"
        self.logger = setup_logger(__name__ + ".FPE")

    def _get_mapping(self, charset: str) -> Dict[str, str]:
        """基于密钥生成确定性映射"""
        char_list = list(charset)
        seed = int(hashlib.sha256(self.key.encode()).hexdigest(), 16)
        random.seed(seed)
        shuffled = char_list[:]
        random.shuffle(shuffled)
        return {c: shuffled[i] for i, c in enumerate(charset)}

    def encrypt(self, plaintext: str, charset: Optional[str] = None) -> str:
        """FPE加密 - 保留格式"""
        if not plaintext:
            return plaintext

        if charset is None:
            if plaintext.isdigit():
                charset = string.digits
            elif plaintext.isalpha():
                charset = string.ascii_letters
            else:
                charset = string.ascii_letters + string.digits

        mapping = self._get_mapping(charset)
        result = []
        for ch in plaintext:
            if ch in mapping:
                result.append(mapping[ch])
            else:
                result.append(ch)
        return "".join(result)

    def decrypt(self, ciphertext: str, charset: Optional[str] = None) -> str:
        """FPE解密"""
        if not ciphertext:
            return ciphertext

        if charset is None:
            if ciphertext.isdigit():
                charset = string.digits
            elif ciphertext.isalpha():
                charset = string.ascii_letters
            else:
                charset = string.ascii_letters + string.digits

        mapping = self._get_mapping(charset)
        reverse_mapping = {v: k for k, v in mapping.items()}

        result = []
        for ch in ciphertext:
            if ch in reverse_mapping:
                result.append(reverse_mapping[ch])
            else:
                result.append(ch)
        return "".join(result)


class DataMaskingEngine:
    """数据脱敏引擎 - 整合所有功能"""

    def __init__(self):
        self.recognizer = SensitiveDataRecognizer()
        self.masker = DataMasker()
        self.fpe = FormatPreservingEncryption()
        self.logger = setup_logger(__name__ + ".DataMaskingEngine")

    def mask_text(self, text: str, level_threshold: SensitivityLevel = SensitivityLevel.LOW) -> str:
        """自动识别并脱敏文本"""
        findings = self.recognizer.recognize(text)
        level_order = {SensitivityLevel.LOW: 1, SensitivityLevel.MEDIUM: 2, SensitivityLevel.HIGH: 3, SensitivityLevel.CRITICAL: 4}
        threshold = level_order[level_threshold]

        result = text
        for finding in sorted(findings, key=lambda x: x["position"][0], reverse=True):
            if level_order.get(SensitivityLevel(finding["level"]), 0) < threshold:
                continue

            match = finding["match"]
            masked = self._apply_mask(match, finding["mask_type"], finding["name"])
            start, end = finding["position"]
            result = result[:start] + masked + result[end:]

        return result

    def _apply_mask(self, value: str, mask_type: str, pattern_name: str) -> str:
        """应用掩码"""
        if mask_type == MaskType.FULL.value:
            return self.masker.mask_full(value)
        elif mask_type == MaskType.HASH.value:
            return self.masker.mask_hash(value)
        elif mask_type == MaskType.TRUNCATE.value:
            return self.masker.mask_truncate(value)
        elif mask_type == MaskType.FPE.value:
            return self.fpe.encrypt(value)
        else:
            if pattern_name == "phone":
                return self.masker.mask_phone(value)
            elif pattern_name == "id_card":
                return self.masker.mask_id_card(value)
            elif pattern_name == "email":
                return self.masker.mask_email(value)
            elif pattern_name == "bank_card":
                return self.masker.mask_bank_card(value)
            return self.masker.mask_partial(value)

    def mask_dict(self, data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """脱敏字典数据"""
        if sensitive_keys is None:
            sensitive_keys = ["password", "token", "secret", "credit_card", "ssn", "phone", "email"]

        result = {}
        for key, value in data.items():
            if any(sk in key.lower() for sk in sensitive_keys):
                if isinstance(value, str):
                    result[key] = self.masker.mask_full(value)
                else:
                    result[key] = "***"
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value, sensitive_keys)
            elif isinstance(value, list):
                result[key] = [self.mask_dict(v, sensitive_keys) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        return result

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        return {
            "patterns": [p.name for p in self.recognizer.patterns],
            "mask_types": [m.value for m in MaskType],
            "fpe_enabled": True,
        }
