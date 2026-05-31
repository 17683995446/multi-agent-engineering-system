"""
阶段79验证脚本：多语言支持模块
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.i18n import I18NManager, Locale, TranslationCatalog, _, get_locale, set_locale


def test_locale_registration():
    """测试区域设置注册"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    assert "zh" in manager.get_available_locales()
    print("✓ 区域设置注册测试通过")


def test_translation_catalog():
    """测试翻译目录"""
    catalog = TranslationCatalog("zh")
    catalog.add("hello", "你好")
    assert catalog.get("hello") == "你好"
    assert catalog.get("missing", "默认") == "默认"
    assert catalog.has("hello") is True
    assert catalog.has("missing") is False
    print("✓ 翻译目录测试通过")


def test_fallback():
    """测试回退机制"""
    zh = TranslationCatalog("zh")
    zh.add("hello", "你好")
    en = TranslationCatalog("en")
    en.add("hello", "Hello")
    en.add("goodbye", "Goodbye")
    zh.set_fallback(en)

    assert zh.get("hello") == "你好"
    assert zh.get("goodbye") == "Goodbye"
    assert zh.has("goodbye") is True
    print("✓ 回退机制测试通过")


def test_translate():
    """测试翻译功能"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.register_locale(Locale("en", "English", "English"))
    manager.add_translations("zh", {"greeting": "你好，{name}！"})
    manager.add_translations("en", {"greeting": "Hello, {name}!"})

    manager.set_locale("zh")
    assert manager.translate("greeting", name="世界") == "你好，世界！"

    manager.set_locale("en")
    assert manager.translate("greeting", name="World") == "Hello, World!"
    print("✓ 翻译功能测试通过")


def test_missing_key():
    """测试缺失键处理"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.set_locale("zh")
    assert manager.translate("nonexistent") == "nonexistent"
    print("✓ 缺失键处理测试通过")


def test_load_from_dict():
    """测试从字典加载"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.load_from_dict("zh", {
        "a": {"b": "嵌套值"},
        "top": "顶层值",
    })
    assert manager.translate("a.b") == "嵌套值"
    assert manager.translate("top") == "顶层值"
    print("✓ 从字典加载测试通过")


def test_get_missing_keys():
    """测试获取缺失键"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.register_locale(Locale("en", "English", "English"))
    manager.add_translations("zh", {"a": "A", "b": "B", "c": "C"})
    manager.add_translations("en", {"a": "A", "b": "B"})

    missing = manager.get_missing_keys("en", reference_locale="zh")
    assert "c" in missing
    assert "a" not in missing
    print("✓ 获取缺失键测试通过")


def test_shortcut_functions():
    """测试快捷函数"""
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.add_translations("zh", {"test": "测试"})
    set_locale("zh")
    assert _("test") == "测试"
    assert get_locale() == "zh"
    print("✓ 快捷函数测试通过")


def test_status():
    """测试状态获取"""
    I18NManager._instance = None
    manager = I18NManager()
    manager.register_locale(Locale("zh", "中文", "中文"))
    manager.add_translations("zh", {"a": "A"})
    status = manager.get_status()
    assert status["current_locale"] == "zh"
    assert "zh" in status["registered_locales"]
    assert status["catalog_counts"]["zh"] == 1
    print("✓ 状态获取测试通过")


def main():
    print("=" * 60)
    print("阶段79验证：多语言支持模块")
    print("=" * 60)

    test_locale_registration()
    test_translation_catalog()
    test_fallback()
    test_translate()
    test_missing_key()
    test_load_from_dict()
    test_get_missing_keys()
    test_shortcut_functions()
    test_status()

    print("=" * 60)
    print("阶段79验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
