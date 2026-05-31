"""
阶段81验证脚本：加密工具模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.crypto_utils import (
    AESKey,
    AsymmetricCrypto,
    CryptoError,
    CryptoManager,
    HashUtils,
    HMACUtils,
    RSAKeyPair,
    SymmetricCrypto,
)


def test_aes_key_generation():
    """测试AES密钥生成"""
    key = AESKey.generate(256)
    assert len(key.key) == 32
    assert key.key_size == 256

    key128 = AESKey.generate(128)
    assert len(key128.key) == 16
    print("✓ AES密钥生成测试通过")


def test_aes_base64():
    """测试AES密钥Base64转换"""
    key = AESKey.generate(256)
    b64 = key.to_base64()
    key2 = AESKey.from_base64(b64)
    assert key.key == key2.key
    print("✓ AES密钥Base64转换测试通过")


def test_aes_encrypt_decrypt():
    """测试AES加密解密"""
    key = AESKey.generate(256)
    plaintext = "Hello, World! 你好，世界！"

    encrypted = SymmetricCrypto.encrypt(plaintext, key)
    assert "nonce" in encrypted
    assert "ciphertext" in encrypted

    decrypted = SymmetricCrypto.decrypt(encrypted, key)
    assert decrypted.decode("utf-8") == plaintext
    print("✓ AES加密解密测试通过")


def test_aes_associated_data():
    """测试AES-GCM关联数据"""
    key = AESKey.generate(256)
    plaintext = "secret data"
    aad = b"additional authenticated data"

    encrypted = SymmetricCrypto.encrypt(plaintext, key, associated_data=aad)
    decrypted = SymmetricCrypto.decrypt(encrypted, key, associated_data=aad)
    assert decrypted.decode("utf-8") == plaintext
    print("✓ AES-GCM关联数据测试通过")


def test_aes_decrypt_failure():
    """测试AES解密失败"""
    key1 = AESKey.generate(256)
    key2 = AESKey.generate(256)
    plaintext = "test"

    encrypted = SymmetricCrypto.encrypt(plaintext, key1)
    try:
        SymmetricCrypto.decrypt(encrypted, key2)
        assert False, "应抛出异常"
    except CryptoError:
        pass
    print("✓ AES解密失败测试通过")


def test_rsa_keypair_generation():
    """测试RSA密钥对生成"""
    pair = RSAKeyPair.generate(2048)
    assert pair.private_key.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert pair.public_key.startswith(b"-----BEGIN PUBLIC KEY-----")
    print("✓ RSA密钥对生成测试通过")


def test_rsa_encrypt_decrypt():
    """测试RSA加密解密"""
    pair = RSAKeyPair.generate(2048)
    plaintext = "Hello, RSA!"

    encrypted = AsymmetricCrypto.encrypt(plaintext, pair)
    decrypted = AsymmetricCrypto.decrypt(encrypted, pair)
    assert decrypted.decode("utf-8") == plaintext
    print("✓ RSA加密解密测试通过")


def test_rsa_sign_verify():
    """测试RSA签名验签"""
    pair = RSAKeyPair.generate(2048)
    message = "message to sign"

    signature = AsymmetricCrypto.sign(message, pair)
    assert AsymmetricCrypto.verify(message, signature, pair) is True
    assert AsymmetricCrypto.verify("wrong message", signature, pair) is False
    print("✓ RSA签名验签测试通过")


def test_sha256():
    """测试SHA256哈希"""
    h1 = HashUtils.sha256("hello")
    h2 = HashUtils.sha256("hello")
    h3 = HashUtils.sha256("world")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64
    print("✓ SHA256哈希测试通过")


def test_sha256_file():
    """测试文件SHA256哈希"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content")
        filepath = f.name

    h1 = HashUtils.sha256_file(filepath)
    h2 = HashUtils.sha256_file(filepath)
    assert h1 == h2
    assert len(h1) == 64

    import os
    os.unlink(filepath)
    print("✓ 文件SHA256哈希测试通过")


def test_pbkdf2():
    """测试PBKDF2密钥派生"""
    result = HashUtils.pbkdf2("password", salt=b"salt", iterations=1000)
    assert "key" in result
    assert "salt" in result
    assert result["iterations"] == 1000

    result2 = HashUtils.pbkdf2("password", salt=b"salt", iterations=1000)
    assert result["key"] == result2["key"]
    print("✓ PBKDF2密钥派生测试通过")


def test_hmac_sign_verify():
    """测试HMAC签名验签"""
    key = "secret_key"
    message = "message"

    sig = HMACUtils.sign(key, message)
    assert HMACUtils.verify(key, message, sig) is True
    assert HMACUtils.verify(key, "wrong", sig) is False
    assert HMACUtils.verify("wrong_key", message, sig) is False
    print("✓ HMAC签名验签测试通过")


def test_hmac_sha512():
    """测试HMAC-SHA512"""
    sig = HMACUtils.sign("key", "msg", algorithm="sha512")
    assert HMACUtils.verify("key", "msg", sig, algorithm="sha512") is True
    print("✓ HMAC-SHA512测试通过")


def test_crypto_manager():
    """测试加密管理器"""
    mgr = CryptoManager()
    aes_key = mgr.generate_aes_key(256)
    assert isinstance(aes_key, AESKey)

    rsa_pair = mgr.generate_rsa_keypair(2048)
    assert isinstance(rsa_pair, RSAKeyPair)

    random_str = mgr.secure_random(16)
    assert len(random_str) > 0

    status = mgr.get_status()
    assert status["symmetric"] == "AES-GCM"
    assert status["asymmetric"] == "RSA-OAEP"
    print("✓ 加密管理器测试通过")


def main():
    print("=" * 60)
    print("阶段81验证：加密工具模块")
    print("=" * 60)

    test_aes_key_generation()
    test_aes_base64()
    test_aes_encrypt_decrypt()
    test_aes_associated_data()
    test_aes_decrypt_failure()
    test_rsa_keypair_generation()
    test_rsa_encrypt_decrypt()
    test_rsa_sign_verify()
    test_sha256()
    test_sha256_file()
    test_pbkdf2()
    test_hmac_sign_verify()
    test_hmac_sha512()
    test_crypto_manager()

    print("=" * 60)
    print("阶段81验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
