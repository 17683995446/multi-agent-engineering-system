"""
阶段85验证脚本：数据脱敏模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.data_masking import (
    DataMasker,
    DataMaskingEngine,
    FormatPreservingEncryption,
    MaskType,
    SensitiveDataRecognizer,
    SensitivePattern,
    SensitivityLevel,
)


def test_recognize_phone():
    """测试手机号识别"""
    recognizer = SensitiveDataRecognizer()
    text = "联系我 13800138000"
    findings = recognizer.recognize(text)
    assert len(findings) == 1
    assert findings[0]["name"] == "phone"
    assert findings[0]["match"] == "13800138000"
    print("✓ 手机号识别测试通过")


def test_recognize_email():
    """测试邮箱识别"""
    recognizer = SensitiveDataRecognizer()
    text = "发送给 user@example.com"
    findings = recognizer.recognize(text)
    assert len(findings) == 1
    assert findings[0]["name"] == "email"
    print("✓ 邮箱识别测试通过")


def test_recognize_id_card():
    """测试身份证号识别"""
    recognizer = SensitiveDataRecognizer()
    text = "身份证号 110101199001011234"
    findings = recognizer.recognize(text)
    names = [f["name"] for f in findings]
    assert "id_card" in names
    print("✓ 身份证号识别测试通过")


def test_recognize_password():
    """测试密码识别"""
    recognizer = SensitiveDataRecognizer()
    text = "password: mysecret123"
    findings = recognizer.recognize(text)
    assert len(findings) == 1
    assert findings[0]["name"] == "password"
    assert findings[0]["level"] == "critical"
    print("✓ 密码识别测试通过")


def test_has_sensitive_data():
    """测试敏感数据判断"""
    recognizer = SensitiveDataRecognizer()
    assert recognizer.has_sensitive_data("电话 13800138000") is True
    assert recognizer.has_sensitive_data("普通文本") is False
    print("✓ 敏感数据判断测试通过")


def test_mask_full():
    """测试完全掩码"""
    assert DataMasker.mask_full("secret") == "******"
    assert DataMasker.mask_full("abc", "#") == "###"
    print("✓ 完全掩码测试通过")


def test_mask_partial():
    """测试部分掩码"""
    assert DataMasker.mask_partial("13800138000", 3, 4) == "138****8000"
    assert DataMasker.mask_partial("abcd", 2, 2) == "****"
    print("✓ 部分掩码测试通过")


def test_mask_hash():
    """测试哈希掩码"""
    h1 = DataMasker.mask_hash("test")
    h2 = DataMasker.mask_hash("test")
    assert h1 == h2
    assert len(h1) == 16
    print("✓ 哈希掩码测试通过")


def test_mask_truncate():
    """测试截断掩码"""
    assert DataMasker.mask_truncate("long_string_here", 4) == "long..."
    assert DataMasker.mask_truncate("ab", 4) == "**"
    print("✓ 截断掩码测试通过")


def test_mask_phone():
    """测试手机号掩码"""
    assert DataMasker.mask_phone("13800138000") == "138****8000"
    print("✓ 手机号掩码测试通过")


def test_mask_id_card():
    """测试身份证号掩码"""
    result = DataMasker.mask_id_card("110101199001011234")
    assert result.startswith("1101")
    assert result.endswith("1234")
    assert "****" in result
    print("✓ 身份证号掩码测试通过")


def test_mask_email():
    """测试邮箱掩码"""
    assert DataMasker.mask_email("user@example.com") == "u**r@example.com"
    assert DataMasker.mask_email("ab@example.com") == "**@example.com"
    print("✓ 邮箱掩码测试通过")


def test_mask_bank_card():
    """测试银行卡号掩码"""
    result = DataMasker.mask_bank_card("6222021234567890123")
    assert result.startswith("6222")
    assert result.endswith("0123")
    assert "****" in result
    print("✓ 银行卡号掩码测试通过")


def test_fpe_encrypt_decrypt():
    """测试FPE加密解密"""
    fpe = FormatPreservingEncryption("test_key")
    plaintext = "1234567890"
    encrypted = fpe.encrypt(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) == len(plaintext)
    assert encrypted.isdigit() == plaintext.isdigit()

    decrypted = fpe.decrypt(encrypted)
    assert decrypted == plaintext
    print("✓ FPE加密解密测试通过")


def test_fpe_alpha():
    """测试FPE字母加密"""
    fpe = FormatPreservingEncryption("test_key")
    plaintext = "HelloWorld"
    encrypted = fpe.encrypt(plaintext)
    assert len(encrypted) == len(plaintext)
    assert encrypted.isalpha() == plaintext.isalpha()

    decrypted = fpe.decrypt(encrypted)
    assert decrypted == plaintext
    print("✓ FPE字母加密测试通过")


def test_engine_mask_text():
    """测试引擎自动脱敏文本"""
    engine = DataMaskingEngine()
    text = "用户 13800138000 的邮箱是 user@example.com"
    masked = engine.mask_text(text)
    assert "138****8000" in masked
    assert "u**r@example.com" in masked
    print("✓ 引擎自动脱敏文本测试通过")


def test_engine_mask_password():
    """测试引擎密码脱敏"""
    engine = DataMaskingEngine()
    text = "password: mysecret"
    masked = engine.mask_text(text)
    assert "mysecret" not in masked
    assert "********" in masked or "password: ********" in masked
    print("✓ 引擎密码脱敏测试通过")


def test_engine_mask_dict():
    """测试引擎字典脱敏"""
    engine = DataMaskingEngine()
    data = {
        "username": "alice",
        "password": "secret123",
        "email": "alice@example.com",
        "phone": "13800138000",
        "nested": {
            "api_token": "abc123",
            "name": "test",
        },
    }
    masked = engine.mask_dict(data)
    assert masked["username"] == "alice"
    assert masked["password"] == "*********"
    assert "***" in masked["email"]
    assert "***" in masked["phone"]
    assert masked["nested"]["api_token"] == "******"
    assert masked["nested"]["name"] == "test"
    print("✓ 引擎字典脱敏测试通过")


def test_engine_status():
    """测试引擎状态"""
    engine = DataMaskingEngine()
    status = engine.get_status()
    assert "phone" in status["patterns"]
    assert "email" in status["patterns"]
    assert "fpe_enabled" in status
    print("✓ 引擎状态测试通过")


def test_add_custom_pattern():
    """测试添加自定义模式"""
    recognizer = SensitiveDataRecognizer()
    pattern = SensitivePattern(
        name="custom_token",
        pattern=__import__("re").compile(r"tk_[a-zA-Z0-9]+"),
        level=SensitivityLevel.HIGH,
        mask_type=MaskType.FULL,
        description="自定义Token",
    )
    recognizer.add_pattern(pattern)
    findings = recognizer.recognize("token: tk_abc123def456789")
    assert len(findings) >= 1
    names = [f["name"] for f in findings]
    assert "custom_token" in names
    print("✓ 添加自定义模式测试通过")


def main():
    print("=" * 60)
    print("阶段85验证：数据脱敏模块")
    print("=" * 60)

    test_recognize_phone()
    test_recognize_email()
    test_recognize_id_card()
    test_recognize_password()
    test_has_sensitive_data()
    test_mask_full()
    test_mask_partial()
    test_mask_hash()
    test_mask_truncate()
    test_mask_phone()
    test_mask_id_card()
    test_mask_email()
    test_mask_bank_card()
    test_fpe_encrypt_decrypt()
    test_fpe_alpha()
    test_engine_mask_text()
    test_engine_mask_password()
    test_engine_mask_dict()
    test_engine_status()
    test_add_custom_pattern()

    print("=" * 60)
    print("阶段85验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
