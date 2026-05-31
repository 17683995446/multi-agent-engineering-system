"""
阶段87验证脚本：隐私保护模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.privacy_protection import (
    PIIType,
    ConsentStatus,
    DataSubjectRight,
    PIIFinding,
    ConsentRecord,
    DataSubjectRequest,
    RegexPIIRecognizer,
    HashAnonymizer,
    MaskAnonymizer,
    GeneralizationAnonymizer,
    DataAnonymizer,
    ConsentManager,
    DataSubjectRightsManager,
    PrivacyProtection,
)


def test_pii_recognize_email():
    """测试邮箱识别"""
    recognizer = RegexPIIRecognizer()
    findings = recognizer.recognize("联系邮箱: user@example.com")
    assert len(findings) == 1
    assert findings[0].pii_type == PIIType.EMAIL
    assert findings[0].value == "user@example.com"
    print("✓ 邮箱识别测试通过")


def test_pii_recognize_phone():
    """测试手机号识别"""
    recognizer = RegexPIIRecognizer()
    findings = recognizer.recognize("手机: 13800138000")
    assert len(findings) == 1
    assert findings[0].pii_type == PIIType.PHONE
    print("✓ 手机号识别测试通过")


def test_pii_recognize_id_card():
    """测试身份证识别"""
    recognizer = RegexPIIRecognizer()
    findings = recognizer.recognize("身份证: 110101199001011234")
    assert len(findings) == 1
    assert findings[0].pii_type == PIIType.ID_CARD
    print("✓ 身份证识别测试通过")


def test_pii_recognize_multiple():
    """测试多PII识别"""
    recognizer = RegexPIIRecognizer()
    text = "邮箱: a@b.com, 手机: 13800138000, IP: 192.168.1.1"
    findings = recognizer.recognize(text)
    types = [f.pii_type for f in findings]
    assert PIIType.EMAIL in types
    assert PIIType.PHONE in types
    assert PIIType.IP_ADDRESS in types
    print("✓ 多PII识别测试通过")


def test_hash_anonymizer():
    """测试哈希匿名化"""
    anon = HashAnonymizer(salt="test")
    result = anon.anonymize("user@example.com", PIIType.EMAIL)
    assert result.startswith("email_")
    assert len(result) == 22
    print("✓ 哈希匿名化测试通过")


def test_mask_anonymizer():
    """测试掩码匿名化"""
    anon = MaskAnonymizer()
    result = anon.anonymize("13800138000", PIIType.PHONE)
    assert "****" in result
    print("✓ 掩码匿名化测试通过")


def test_generalization_anonymizer():
    """测试泛化匿名化"""
    anon = GeneralizationAnonymizer()
    email = anon.anonymize("user@example.com", PIIType.EMAIL)
    assert "***" in email
    phone = anon.anonymize("13800138000", PIIType.PHONE)
    assert phone == "138****8000"
    idcard = anon.anonymize("110101199001011234", PIIType.ID_CARD)
    assert idcard == "110101********1234"
    print("✓ 泛化匿名化测试通过")


def test_data_anonymizer_text():
    """测试文本匿名化"""
    anonymizer = DataAnonymizer()
    text = "邮箱: user@example.com, 手机: 13800138000"
    result = anonymizer.anonymize_text(text, strategy="generalize")
    assert "user@example.com" not in result
    assert "13800138000" not in result
    print("✓ 文本匿名化测试通过")


def test_data_anonymizer_dict():
    """测试字典匿名化"""
    anonymizer = DataAnonymizer()
    data = {"name": "张三", "email": "zs@example.com", "age": 25}
    result = anonymizer.anonymize_dict(data, strategy="mask")
    assert "****" in result["name"] or result["name"] != "张三"
    assert "****" in result["email"] or result["email"] != "zs@example.com"
    assert result["age"] == 25
    print("✓ 字典匿名化测试通过")


def test_consent_manager_grant():
    """测试同意授予"""
    mgr = ConsentManager()
    mgr.grant_consent("user_1", "marketing")
    assert mgr.check_consent("user_1", "marketing") is True
    print("✓ 同意授予测试通过")


def test_consent_manager_revoke():
    """测试同意撤销"""
    mgr = ConsentManager()
    mgr.grant_consent("user_1", "marketing")
    mgr.revoke_consent("user_1", "marketing")
    assert mgr.check_consent("user_1", "marketing") is False
    print("✓ 同意撤销测试通过")


def test_consent_manager_expired():
    """测试同意过期"""
    from datetime import datetime, timedelta
    mgr = ConsentManager()
    past = datetime.now() - timedelta(days=1)
    mgr.grant_consent("user_1", "marketing", expires_at=past)
    assert mgr.check_consent("user_1", "marketing") is False
    print("✓ 同意过期测试通过")


def test_rights_manager_access():
    """测试访问权利"""
    mgr = DataSubjectRightsManager()
    mgr.register_data("user_1", {"name": "张三", "email": "zs@example.com"})
    request = mgr.submit_request("user_1", DataSubjectRight.ACCESS)
    result = mgr.process_request(request)
    assert result.status == "completed"
    assert result.result["data"]["name"] == "张三"
    print("✓ 访问权利测试通过")


def test_rights_manager_erasure():
    """测试删除权利"""
    mgr = DataSubjectRightsManager()
    mgr.register_data("user_1", {"name": "张三"})
    request = mgr.submit_request("user_1", DataSubjectRight.ERASURE)
    result = mgr.process_request(request)
    assert result.result["erased"] is True
    assert "user_1" not in mgr._data_store
    print("✓ 删除权利测试通过")


def test_rights_manager_rectification():
    """测试更正权利"""
    mgr = DataSubjectRightsManager()
    mgr.register_data("user_1", {"name": "张三"})
    request = mgr.submit_request("user_1", DataSubjectRight.RECTIFICATION)
    result = mgr.process_request(request, updates={"name": "张三（已更正）"})
    assert result.result["updated"] is True
    assert mgr._data_store["user_1"]["name"] == "张三（已更正）"
    print("✓ 更正权利测试通过")


def test_rights_manager_portability():
    """测试可携带权利"""
    mgr = DataSubjectRightsManager()
    mgr.register_data("user_1", {"name": "张三"})
    request = mgr.submit_request("user_1", DataSubjectRight.PORTABILITY)
    result = mgr.process_request(request)
    assert result.result["format"] == "json"
    assert "export_timestamp" in result.result
    print("✓ 可携带权利测试通过")


def test_privacy_protection_integration():
    """测试隐私保护主类集成"""
    privacy = PrivacyProtection()
    text = "邮箱: test@example.com, 手机: 13800138000"
    findings = privacy.scan_pii(text)
    assert len(findings) == 2

    anonymized = privacy.anonymize(text)
    assert "test@example.com" not in anonymized

    privacy.consent_manager.grant_consent("u1", "analytics")
    assert privacy.check_processing_allowed("u1", "analytics") is True

    privacy.rights_manager.register_data("u1", {"name": "Test"})
    req = privacy.handle_data_request("u1", DataSubjectRight.ACCESS)
    assert req.status == "completed"

    report = privacy.get_privacy_report("u1")
    assert report["data_registered"] is True
    assert "analytics" in report["consents"]
    print("✓ 隐私保护主类集成测试通过")


def main():
    print("=" * 60)
    print("阶段87验证：隐私保护模块")
    print("=" * 60)

    test_pii_recognize_email()
    test_pii_recognize_phone()
    test_pii_recognize_id_card()
    test_pii_recognize_multiple()
    test_hash_anonymizer()
    test_mask_anonymizer()
    test_generalization_anonymizer()
    test_data_anonymizer_text()
    test_data_anonymizer_dict()
    test_consent_manager_grant()
    test_consent_manager_revoke()
    test_consent_manager_expired()
    test_rights_manager_access()
    test_rights_manager_erasure()
    test_rights_manager_rectification()
    test_rights_manager_portability()
    test_privacy_protection_integration()

    print("=" * 60)
    print("阶段87验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
