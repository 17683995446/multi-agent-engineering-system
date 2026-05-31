"""
多语言支持模块（i18n）
遵循第一性原理：国际化与本地化

核心功能：
1. 国际化
2. 本地化
3. 翻译管理
4. 语言切换
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class I18NError(Exception):
    """国际化异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@dataclass
class Locale:
    """区域设置"""
    code: str
    name: str
    native_name: str
    direction: str = "ltr"  # ltr or rtl
    fallback: Optional[str] = None


class TranslationCatalog:
    """翻译目录"""

    def __init__(self, locale: str):
        self.locale = locale
        self._messages: Dict[str, str] = {}
        self._fallback_catalog: Optional[TranslationCatalog] = None

    def add(self, key: str, translation: str) -> None:
        """添加翻译"""
        self._messages[key] = translation

    def add_many(self, translations: Dict[str, str]) -> None:
        """批量添加翻译"""
        self._messages.update(translations)

    def get(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译"""
        if key in self._messages:
            return self._messages[key]
        if self._fallback_catalog:
            return self._fallback_catalog.get(key, default)
        return default or key

    def has(self, key: str) -> bool:
        """检查是否存在翻译"""
        if key in self._messages:
            return True
        if self._fallback_catalog:
            return self._fallback_catalog.has(key)
        return False

    def set_fallback(self, catalog: TranslationCatalog) -> None:
        """设置回退目录"""
        self._fallback_catalog = catalog

    def keys(self) -> List[str]:
        """获取所有键"""
        keys = set(self._messages.keys())
        if self._fallback_catalog:
            keys.update(self._fallback_catalog.keys())
        return list(keys)


class I18NManager:
    """
    国际化管理器

    核心功能：
    - 多语言翻译管理
    - 动态语言切换
    - 参数插值
    - 回退机制
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._catalogs: Dict[str, TranslationCatalog] = {}
        self._locales: Dict[str, Locale] = {}
        self._current_locale: str = "zh"
        self._default_locale: str = "zh"
        self._initialized = True
        logger.info("国际化管理器初始化完成")

    def register_locale(self, locale: Locale) -> None:
        """注册区域设置"""
        self._locales[locale.code] = locale
        if locale.code not in self._catalogs:
            self._catalogs[locale.code] = TranslationCatalog(locale.code)
        logger.info(f"注册区域设置: {locale.code} ({locale.name})")

    def add_translation(self, locale: str, key: str, translation: str) -> None:
        """添加翻译"""
        catalog = self._get_or_create_catalog(locale)
        catalog.add(key, translation)

    def add_translations(self, locale: str, translations: Dict[str, str]) -> None:
        """批量添加翻译"""
        catalog = self._get_or_create_catalog(locale)
        catalog.add_many(translations)

    def set_locale(self, locale: str) -> None:
        """设置当前语言"""
        if locale not in self._catalogs:
            logger.warning(f"语言 {locale} 未注册，使用默认语言")
            locale = self._default_locale
        self._current_locale = locale
        logger.info(f"当前语言切换为: {locale}")

    def get_locale(self) -> str:
        """获取当前语言"""
        return self._current_locale

    def get_available_locales(self) -> List[str]:
        """获取可用语言列表"""
        return list(self._catalogs.keys())

    def translate(self, key: str, locale: Optional[str] = None, **kwargs) -> str:
        """翻译文本"""
        target_locale = locale or self._current_locale
        catalog = self._catalogs.get(target_locale)
        if not catalog:
            # 尝试回退到默认语言
            catalog = self._catalogs.get(self._default_locale)
        if not catalog:
            return self._interpolate(key, **kwargs)

        text = catalog.get(key, key)
        return self._interpolate(text, **kwargs)

    def _interpolate(self, text: str, **kwargs) -> str:
        """参数插值"""
        if not kwargs:
            return text
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    def _get_or_create_catalog(self, locale: str) -> TranslationCatalog:
        if locale not in self._catalogs:
            self._catalogs[locale] = TranslationCatalog(locale)
        return self._catalogs[locale]

    def set_fallback(self, locale: str, fallback_locale: str) -> None:
        """设置回退语言"""
        catalog = self._catalogs.get(locale)
        fallback = self._catalogs.get(fallback_locale)
        if catalog and fallback:
            catalog.set_fallback(fallback)
            logger.info(f"设置 {locale} 的回退语言为 {fallback_locale}")

    def load_from_dict(self, locale: str, data: Dict[str, Any]) -> None:
        """从字典加载翻译"""
        flattened = {}
        self._flatten_dict(data, "", flattened)
        self.add_translations(locale, flattened)

    def _flatten_dict(self, data: Dict[str, Any], prefix: str, result: Dict[str, str]) -> None:
        """扁平化嵌套字典"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_dict(value, full_key, result)
            else:
                result[full_key] = str(value)

    def get_missing_keys(self, locale: str, reference_locale: Optional[str] = None) -> List[str]:
        """获取缺失的翻译键"""
        ref = reference_locale or self._default_locale
        ref_catalog = self._catalogs.get(ref)
        target_catalog = self._catalogs.get(locale)
        if not ref_catalog:
            return []
        ref_keys = set(ref_catalog.keys())
        if not target_catalog:
            return list(ref_keys)
        target_keys = set(target_catalog.keys())
        return list(ref_keys - target_keys)

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_locale": self._current_locale,
            "default_locale": self._default_locale,
            "registered_locales": list(self._locales.keys()),
            "catalog_counts": {k: len(v.keys()) for k, v in self._catalogs.items()},
        }


# 便捷函数
def _(key: str, **kwargs) -> str:
    """快捷翻译函数"""
    return I18NManager().translate(key, **kwargs)


def set_locale(locale: str) -> None:
    """快捷设置语言"""
    I18NManager().set_locale(locale)


def get_locale() -> str:
    """快捷获取语言"""
    return I18NManager().get_locale()


def demo_i18n():
    """演示多语言支持"""
    print("=" * 60)
    print("多语言支持演示")
    print("=" * 60)
    print()

    manager = I18NManager()

    print("1. 注册区域设置:")
    manager.register_locale(Locale("zh", "中文", "中文", fallback="en"))
    manager.register_locale(Locale("en", "English", "English"))
    manager.register_locale(Locale("ja", "日本語", "日本語", fallback="en"))
    print("   ✓ 已注册: zh, en, ja")
    print()

    print("2. 加载翻译:")
    manager.load_from_dict("zh", {
        "greeting": "你好，{name}！",
        "farewell": "再见",
        "items.count": "你有 {count} 条消息",
    })
    manager.load_from_dict("en", {
        "greeting": "Hello, {name}!",
        "farewell": "Goodbye",
        "items.count": "You have {count} messages",
    })
    manager.load_from_dict("ja", {
        "greeting": "こんにちは、{name}さん！",
    })
    print("   ✓ 翻译已加载")
    print()

    print("3. 中文翻译:")
    manager.set_locale("zh")
    print(f"   ✓ {manager.translate('greeting', name='世界')}")
    print(f"   ✓ {manager.translate('items.count', count=5)}")
    print()

    print("4. 英文翻译:")
    manager.set_locale("en")
    print(f"   ✓ {manager.translate('greeting', name='World')}")
    print(f"   ✓ {manager.translate('items.count', count=3)}")
    print()

    print("5. 日文翻译（含回退）:")
    manager.set_locale("ja")
    manager.set_fallback("ja", "en")
    print(f"   ✓ {manager.translate('greeting', name='World')}")
    print(f"   ✓ farewell 回退到英文: {manager.translate('farewell')}")
    print()

    print("6. 缺失翻译检测:")
    missing = manager.get_missing_keys("ja", reference_locale="en")
    print(f"   ✓ ja 缺失的键: {missing}")
    print()

    print("7. 快捷函数:")
    set_locale("zh")
    print(f"   ✓ _('greeting', name='用户') = {_('greeting', name='用户')}")
    print(f"   ✓ get_locale() = {get_locale()}")
    print()

    print("8. 状态信息:")
    status = manager.get_status()
    print(f"   ✓ {status}")
    print()

    print("=" * 60)
    print("多语言支持演示完成")
    print("=" * 60)
    print()
    print("✓ 国际化")
    print("✓ 本地化")
    print("✓ 翻译管理")
    print("✓ 语言切换")
    print()


if __name__ == "__main__":
    demo_i18n()
