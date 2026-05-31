"""
加密工具模块
遵循第一性原理：信息最小熵公理

核心功能：
1. 对称加密（AES-GCM）
2. 非对称加密（RSA）
3. 哈希（SHA256）
4. HMAC签名
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Optional, Union

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from common.utils import setup_logger

logger = setup_logger(__name__)


class CryptoError(Exception):
    """加密操作异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@dataclass
class AESKey:
    """AES密钥数据类"""
    key: bytes
    key_size: int = 256

    @classmethod
    def generate(cls, key_size: int = 256) -> "AESKey":
        """生成随机AES密钥"""
        if key_size not in (128, 192, 256):
            raise CryptoError(f"不支持的AES密钥长度: {key_size}")
        key = AESGCM.generate_key(bit_length=key_size)
        return cls(key=key, key_size=key_size)

    def to_base64(self) -> str:
        """转为Base64字符串"""
        return base64.b64encode(self.key).decode("utf-8")

    @classmethod
    def from_base64(cls, b64_str: str, key_size: int = 256) -> "AESKey":
        """从Base64字符串加载"""
        key = base64.b64decode(b64_str)
        return cls(key=key, key_size=key_size)


@dataclass
class RSAKeyPair:
    """RSA密钥对数据类"""
    private_key: bytes
    public_key: bytes
    key_size: int = 2048

    @classmethod
    def generate(cls, key_size: int = 2048) -> "RSAKeyPair":
        """生成RSA密钥对"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return cls(private_key=private_pem, public_key=public_pem, key_size=key_size)

    def get_private_key_obj(self):
        """获取私钥对象"""
        return serialization.load_pem_private_key(self.private_key, password=None)

    def get_public_key_obj(self):
        """获取公钥对象"""
        return serialization.load_pem_public_key(self.public_key)


class SymmetricCrypto:
    """对称加密（AES-GCM）"""

    @staticmethod
    def encrypt(plaintext: Union[str, bytes], key: Union[AESKey, bytes], associated_data: Optional[bytes] = None) -> dict:
        """
        AES-GCM加密
        返回包含nonce、ciphertext、tag的字典
        """
        if isinstance(key, AESKey):
            key_bytes = key.key
        else:
            key_bytes = key

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        aesgcm = AESGCM(key_bytes)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

        return {
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
        }

    @staticmethod
    def decrypt(ciphertext_dict: dict, key: Union[AESKey, bytes], associated_data: Optional[bytes] = None) -> bytes:
        """
        AES-GCM解密
        """
        if isinstance(key, AESKey):
            key_bytes = key.key
        else:
            key_bytes = key

        nonce = base64.b64decode(ciphertext_dict["nonce"])
        ciphertext = base64.b64decode(ciphertext_dict["ciphertext"])

        aesgcm = AESGCM(key_bytes)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
            return plaintext
        except Exception as e:
            raise CryptoError(f"AES解密失败: {e}")


class AsymmetricCrypto:
    """非对称加密（RSA）"""

    @staticmethod
    def encrypt(plaintext: Union[str, bytes], public_key: Union[RSAKeyPair, bytes]) -> str:
        """
        RSA公钥加密
        """
        if isinstance(public_key, RSAKeyPair):
            pub_key = public_key.get_public_key_obj()
        else:
            pub_key = serialization.load_pem_public_key(public_key)

        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        ciphertext = pub_key.encrypt(
            plaintext,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode("utf-8")

    @staticmethod
    def decrypt(ciphertext_b64: str, private_key: Union[RSAKeyPair, bytes]) -> bytes:
        """
        RSA私钥解密
        """
        if isinstance(private_key, RSAKeyPair):
            priv_key = private_key.get_private_key_obj()
        else:
            priv_key = serialization.load_pem_private_key(private_key, password=None)

        ciphertext = base64.b64decode(ciphertext_b64)
        try:
            plaintext = priv_key.decrypt(
                ciphertext,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return plaintext
        except Exception as e:
            raise CryptoError(f"RSA解密失败: {e}")

    @staticmethod
    def sign(message: Union[str, bytes], private_key: Union[RSAKeyPair, bytes]) -> str:
        """
        RSA私钥签名
        """
        if isinstance(private_key, RSAKeyPair):
            priv_key = private_key.get_private_key_obj()
        else:
            priv_key = serialization.load_pem_private_key(private_key, password=None)

        if isinstance(message, str):
            message = message.encode("utf-8")

        signature = priv_key.sign(
            message,
            asym_padding.PSS(
                mgf=asym_padding.MGF1(hashes.SHA256()),
                salt_length=asym_padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify(message: Union[str, bytes], signature_b64: str, public_key: Union[RSAKeyPair, bytes]) -> bool:
        """
        RSA公钥验签
        """
        if isinstance(public_key, RSAKeyPair):
            pub_key = public_key.get_public_key_obj()
        else:
            pub_key = serialization.load_pem_public_key(public_key)

        if isinstance(message, str):
            message = message.encode("utf-8")

        signature = base64.b64decode(signature_b64)
        try:
            pub_key.verify(
                signature,
                message,
                asym_padding.PSS(
                    mgf=asym_padding.MGF1(hashes.SHA256()),
                    salt_length=asym_padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False


class HashUtils:
    """哈希工具"""

    @staticmethod
    def sha256(data: Union[str, bytes]) -> str:
        """SHA256哈希"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha256_file(filepath: str) -> str:
        """文件SHA256哈希"""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def md5(data: Union[str, bytes]) -> str:
        """MD5哈希（不推荐用于安全场景）"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def pbkdf2(password: Union[str, bytes], salt: Optional[bytes] = None, iterations: int = 100000, dklen: int = 32) -> dict:
        """PBKDF2密钥派生"""
        if isinstance(password, str):
            password = password.encode("utf-8")
        if salt is None:
            salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password, salt, iterations, dklen=dklen)
        return {
            "key": base64.b64encode(key).decode("utf-8"),
            "salt": base64.b64encode(salt).decode("utf-8"),
            "iterations": iterations,
        }


class HMACUtils:
    """HMAC签名工具"""

    @staticmethod
    def sign(key: Union[str, bytes], message: Union[str, bytes], algorithm: str = "sha256") -> str:
        """HMAC签名"""
        if isinstance(key, str):
            key = key.encode("utf-8")
        if isinstance(message, str):
            message = message.encode("utf-8")

        if algorithm == "sha256":
            sig = hmac.new(key, message, hashlib.sha256).digest()
        elif algorithm == "sha512":
            sig = hmac.new(key, message, hashlib.sha512).digest()
        else:
            raise CryptoError(f"不支持的HMAC算法: {algorithm}")

        return base64.b64encode(sig).decode("utf-8")

    @staticmethod
    def verify(key: Union[str, bytes], message: Union[str, bytes], signature_b64: str, algorithm: str = "sha256") -> bool:
        """HMAC验签"""
        expected = HMACUtils.sign(key, message, algorithm)
        return hmac.compare_digest(expected, signature_b64)


class CryptoManager:
    """加密管理器 - 整合所有加密功能"""

    def __init__(self):
        self.symmetric = SymmetricCrypto()
        self.asymmetric = AsymmetricCrypto()
        self.hash = HashUtils()
        self.hmac = HMACUtils()
        self.logger = setup_logger(__name__ + ".CryptoManager")

    def generate_aes_key(self, key_size: int = 256) -> AESKey:
        """生成AES密钥"""
        return AESKey.generate(key_size)

    def generate_rsa_keypair(self, key_size: int = 2048) -> RSAKeyPair:
        """生成RSA密钥对"""
        return RSAKeyPair.generate(key_size)

    def secure_random(self, length: int = 32) -> str:
        """生成安全随机字符串"""
        return base64.b64encode(secrets.token_bytes(length)).decode("utf-8")

    def get_status(self) -> dict:
        """获取加密管理器状态"""
        return {
            "symmetric": "AES-GCM",
            "asymmetric": "RSA-OAEP",
            "hash": "SHA256",
            "hmac": "HMAC-SHA256",
        }
