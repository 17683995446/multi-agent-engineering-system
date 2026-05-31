#!/usr/bin/env python3
"""
阶段46验证脚本 - 插件系统
测试内容：
1. 插件系统初始化
2. 插件注册和加载
3. 插件启用/禁用
4. 钩子机制
5. 插件依赖管理
"""

import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.plugin_system import (
    PluginBase,
    PluginManager,
    PluginRegistry,
    HookManager,
    PluginStatus,
    PluginMetadata,
    PluginException,
    PluginDependencyException,
)


# 测试用插件定义
class TestPluginA(PluginBase):
    metadata = PluginMetadata(
        name="test_plugin_a",
        version="1.0.0",
        description="测试插件A",
        author="test",
        hooks=["before_process", "after_process"],
        priority=10,
    )
    
    def __init__(self):
        super().__init__()
        self.initialized = False
        self.started = False
        self.enabled = False
        self.disabled = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return super().initialize()
    
    def startup(self) -> bool:
        self.started = True
        return super().startup()
    
    def on_enable(self):
        self.enabled = True
    
    def on_disable(self):
        self.disabled = True
    
    def process(self, data):
        return f"A processed: {data}"


class TestPluginB(PluginBase):
    metadata = PluginMetadata(
        name="test_plugin_b",
        version="2.0.0",
        description="测试插件B，依赖A",
        author="test",
        dependencies=["test_plugin_a"],
        hooks=["before_process"],
        priority=5,
    )
    
    def __init__(self):
        super().__init__()
        self.initialized = False
    
    def initialize(self) -> bool:
        self.initialized = True
        return super().initialize()
    
    def process(self, data):
        return f"B processed: {data}"


class TestPluginC(PluginBase):
    metadata = PluginMetadata(
        name="test_plugin_c",
        version="1.0.0",
        description="测试插件C，依赖B",
        author="test",
        dependencies=["test_plugin_b"],
        priority=1,
    )
    
    def process(self, data):
        return f"C processed: {data}"


class TestPluginD(PluginBase):
    metadata = PluginMetadata(
        name="test_plugin_d",
        version="1.0.0",
        description="测试插件D，循环依赖测试",
        author="test",
        dependencies=["test_plugin_e"],
    )


class TestPluginE(PluginBase):
    metadata = PluginMetadata(
        name="test_plugin_e",
        version="1.0.0",
        description="测试插件E，循环依赖测试",
        author="test",
        dependencies=["test_plugin_d"],
    )


def test_plugin_system_initialization():
    """测试1: 插件系统初始化"""
    print("\n" + "=" * 60)
    print("测试1: 插件系统初始化")
    print("=" * 60)
    
    manager = PluginManager()
    
    assert manager.registry is not None, "注册表未初始化"
    assert manager.hook_manager is not None, "钩子管理器未初始化"
    assert isinstance(manager.registry, PluginRegistry), "注册表类型错误"
    assert isinstance(manager.hook_manager, HookManager), "钩子管理器类型错误"
    
    print("✓ PluginManager 初始化成功")
    print("✓ PluginRegistry 初始化成功")
    print("✓ HookManager 初始化成功")
    print("✓ 所有组件正确关联")
    
    return manager


def test_plugin_registration_and_loading(manager: PluginManager):
    """测试2: 插件注册和加载"""
    print("\n" + "=" * 60)
    print("测试2: 插件注册和加载")
    print("=" * 60)
    
    # 加载插件A
    plugin_a = manager.load_plugin(TestPluginA)
    assert plugin_a is not None, "插件A加载失败"
    assert plugin_a.name == "test_plugin_a", "插件A名称错误"
    assert plugin_a.version == "1.0.0", "插件A版本错误"
    assert plugin_a.status == PluginStatus.REGISTERED, "插件A状态错误"
    assert plugin_a.initialized, "插件A未初始化"
    print("✓ 插件A加载成功")
    
    # 验证注册表
    assert "test_plugin_a" in manager.list_plugins(), "插件A未在列表中"
    assert manager.get_plugin("test_plugin_a") is plugin_a, "插件A获取失败"
    print("✓ 插件A已注册到注册表")
    
    # 加载插件B
    plugin_b = manager.load_plugin(TestPluginB)
    assert plugin_b is not None, "插件B加载失败"
    assert plugin_b.name == "test_plugin_b", "插件B名称错误"
    print("✓ 插件B加载成功")
    
    # 验证注册类
    classes = manager.registry.list_classes()
    assert "test_plugin_a" in classes, "插件类A未注册"
    assert "test_plugin_b" in classes, "插件类B未注册"
    print("✓ 插件类正确注册")
    
    # 验证上下文
    plugin_a.set_context("key1", "value1")
    assert plugin_a.get_context("key1") == "value1", "上下文设置失败"
    assert plugin_a.get_context("nonexist", "default") == "default", "上下文默认值失败"
    print("✓ 插件上下文功能正常")
    
    return True


def test_plugin_enable_disable(manager: PluginManager):
    """测试3: 插件启用/禁用"""
    print("\n" + "=" * 60)
    print("测试3: 插件启用/禁用")
    print("=" * 60)
    
    # 启用插件A
    result = manager.enable_plugin("test_plugin_a")
    assert result is True, "插件A启用失败"
    
    plugin_a = manager.get_plugin("test_plugin_a")
    assert plugin_a.status == PluginStatus.ENABLED, "插件A状态不是ENABLED"
    assert plugin_a.started, "插件A未启动"
    assert plugin_a.enabled, "插件A on_enable未调用"
    print("✓ 插件A启用成功")
    
    # 验证已启用列表
    enabled = manager.list_enabled_plugins()
    assert "test_plugin_a" in enabled, "插件A不在已启用列表"
    print("✓ 已启用插件列表正确")
    
    # 禁用插件A
    result = manager.disable_plugin("test_plugin_a")
    assert result is True, "插件A禁用失败"
    assert plugin_a.status == PluginStatus.DISABLED, "插件A状态不是DISABLED"
    assert plugin_a.disabled, "插件A on_disable未调用"
    print("✓ 插件A禁用成功")
    
    # 验证已启用列表
    enabled = manager.list_enabled_plugins()
    assert "test_plugin_a" not in enabled, "插件A仍在已启用列表"
    print("✓ 已启用插件列表更新正确")
    
    # 重复启用
    manager.enable_plugin("test_plugin_a")
    result = manager.enable_plugin("test_plugin_a")
    assert result is True, "重复启用失败"
    print("✓ 重复启用处理正确")
    
    # 禁用所有
    manager.load_plugin(TestPluginC)
    manager.enable_plugin("test_plugin_b")
    manager.enable_plugin("test_plugin_c")
    
    results = manager.disable_all()
    assert all(results.values()), "禁用所有插件失败"
    print("✓ 禁用所有插件成功")
    
    return True


def test_hook_mechanism(manager: PluginManager):
    """测试4: 钩子机制"""
    print("\n" + "=" * 60)
    print("测试4: 钩子机制")
    print("=" * 60)
    
    hook_mgr = HookManager()
    
    # 注册钩子
    results_collector = []
    
    def callback1(data):
        results_collector.append("callback1")
        return data + "_cb1"
    
    def callback2(data):
        results_collector.append("callback2")
        return data + "_cb2"
    
    def callback3(data):
        results_collector.append("callback3")
        return data + "_cb3"
    
    hook_mgr.register_hook("test_hook", callback1, priority=2, plugin_name="plugin1")
    hook_mgr.register_hook("test_hook", callback2, priority=1, plugin_name="plugin2")
    hook_mgr.register_hook("test_hook", callback3, priority=3, plugin_name="plugin3")
    print("✓ 钩子注册成功")
    
    # 验证优先级排序
    callbacks = hook_mgr.get_hook_callbacks("test_hook")
    assert len(callbacks) == 3, "钩子回调数量错误"
    assert callbacks[0]["priority"] == 1, "优先级排序错误"
    assert callbacks[2]["priority"] == 3, "优先级排序错误"
    print("✓ 钩子优先级排序正确")
    
    # 执行钩子
    results = hook_mgr.execute_hook("test_hook", "input")
    assert len(results) == 3, "钩子执行结果数量错误"
    assert results[0] == "input_cb2", "钩子执行结果错误"
    assert results[1] == "input_cb1", "钩子执行结果错误"
    assert results[2] == "input_cb3", "钩子执行结果错误"
    print("✓ 钩子执行成功，结果正确")
    
    # 链式执行
    result = hook_mgr.execute_hook_chain("test_hook", "start")
    assert result == "start_cb2_cb1_cb3", f"链式执行结果错误: {result}"
    print("✓ 钩子链式执行成功")
    
    # 列出钩子
    hooks = hook_mgr.list_hooks()
    assert "test_hook" in hooks, "钩子列表错误"
    print("✓ 钩子列表正确")
    
    # 注销单个回调
    hook_mgr.unregister_hook("test_hook", callback=callback3)
    callbacks = hook_mgr.get_hook_callbacks("test_hook")
    assert len(callbacks) == 2, "注销后回调数量错误"
    print("✓ 注销单个钩子回调成功")
    
    # 按插件注销
    hook_mgr.unregister_hook("test_hook", plugin_name="plugin1")
    callbacks = hook_mgr.get_hook_callbacks("test_hook")
    assert len(callbacks) == 1, "按插件注销后数量错误"
    print("✓ 按插件注销钩子成功")
    
    # 清空钩子
    hook_mgr.clear()
    assert len(hook_mgr.list_hooks()) == 0, "清空后钩子数量错误"
    print("✓ 清空所有钩子成功")
    
    # 测试PluginManager代理
    manager.register_hook("proxy_hook", callback1, priority=0, plugin_name="test")
    results = manager.execute_hook("proxy_hook", "data")
    assert results == ["data_cb1"], "代理钩子执行失败"
    print("✓ PluginManager钩子代理正常")
    
    return True


def test_plugin_dependency_management(manager: PluginManager):
    """测试5: 插件依赖管理"""
    print("\n" + "=" * 60)
    print("测试5: 插件依赖管理")
    print("=" * 60)
    
    # 清理之前的状态
    manager.unload_all()
    
    # 加载依赖链: C -> B -> A
    plugin_a = manager.load_plugin(TestPluginA)
    plugin_b = manager.load_plugin(TestPluginB)
    plugin_c = manager.load_plugin(TestPluginC)
    print("✓ 依赖链插件加载成功")
    
    # 启用C，应该自动启用B和A
    result = manager.enable_plugin("test_plugin_c")
    assert result is True, "插件C启用失败"
    
    assert plugin_a.status == PluginStatus.ENABLED, "依赖A未自动启用"
    assert plugin_b.status == PluginStatus.ENABLED, "依赖B未自动启用"
    assert plugin_c.status == PluginStatus.ENABLED, "插件C未启用"
    print("✓ 依赖自动解析并启用成功")
    
    # 验证启用顺序
    enabled_list = manager.list_enabled_plugins()
    assert "test_plugin_a" in enabled_list
    assert "test_plugin_b" in enabled_list
    assert "test_plugin_c" in enabled_list
    print("✓ 所有依赖插件已启用")
    
    # 测试缺失依赖
    class TestPluginMissing(PluginBase):
        metadata = PluginMetadata(
            name="test_plugin_missing",
            version="1.0.0",
            dependencies=["nonexistent_plugin"],
        )
    
    manager.load_plugin(TestPluginMissing)
    try:
        manager.enable_plugin("test_plugin_missing")
        assert False, "应该抛出依赖异常"
    except PluginDependencyException as e:
        assert "nonexistent_plugin" in str(e), "异常信息错误"
        print("✓ 缺失依赖检测正确")
    
    # 测试循环依赖
    manager.unload_all()
    manager.load_plugin(TestPluginD)
    manager.load_plugin(TestPluginE)
    
    try:
        manager.enable_plugin("test_plugin_d")
        assert False, "应该抛出循环依赖异常"
    except PluginDependencyException as e:
        assert "Circular dependency" in str(e), "循环依赖异常信息错误"
        print("✓ 循环依赖检测正确")
    
    # 测试enable_all
    manager.unload_all()
    manager.load_plugin(TestPluginA)
    manager.load_plugin(TestPluginB)
    
    results = manager.enable_all()
    assert results["test_plugin_a"] is True, "enable_all A失败"
    assert results["test_plugin_b"] is True, "enable_all B失败"
    print("✓ enable_all 成功")
    
    # 测试卸载
    result = manager.unload_plugin("test_plugin_b")
    assert result is True, "卸载B失败"
    assert manager.get_plugin("test_plugin_b") is None, "B仍在注册表中"
    print("✓ 插件卸载成功")
    
    return True


def test_plugin_metadata():
    """测试6: 插件元数据"""
    print("\n" + "=" * 60)
    print("测试6: 插件元数据")
    print("=" * 60)
    
    meta = PluginMetadata(
        name="test_meta",
        version="1.2.3",
        description="测试描述",
        author="测试作者",
        dependencies=["dep1", "dep2"],
        hooks=["hook1"],
        priority=5,
    )
    
    assert meta.name == "test_meta"
    assert meta.version == "1.2.3"
    assert meta.description == "测试描述"
    assert meta.author == "测试作者"
    assert meta.dependencies == ["dep1", "dep2"]
    assert meta.hooks == ["hook1"]
    assert meta.priority == 5
    print("✓ 插件元数据正确")
    
    # 默认值
    meta2 = PluginMetadata(name="default_test")
    assert meta2.version == "1.0.0"
    assert meta2.dependencies == []
    assert meta2.priority == 0
    print("✓ 插件元数据默认值正确")
    
    return True


def test_plugin_status_enum():
    """测试7: 插件状态枚举"""
    print("\n" + "=" * 60)
    print("测试7: 插件状态枚举")
    print("=" * 60)
    
    assert PluginStatus.UNLOADED.value == "unloaded"
    assert PluginStatus.LOADED.value == "loaded"
    assert PluginStatus.REGISTERED.value == "registered"
    assert PluginStatus.ENABLED.value == "enabled"
    assert PluginStatus.DISABLED.value == "disabled"
    assert PluginStatus.ERROR.value == "error"
    print("✓ 插件状态枚举值正确")
    
    return True


def test_plugin_exceptions():
    """测试8: 插件异常"""
    print("\n" + "=" * 60)
    print("测试8: 插件异常")
    print("=" * 60)
    
    try:
        raise PluginException("测试插件异常")
    except PluginException as e:
        assert e.code == "PLUGIN_ERROR"
        assert "测试插件异常" in e.message
        print("✓ PluginException 正常")
    
    try:
        raise PluginDependencyException("测试依赖异常")
    except PluginDependencyException as e:
        assert e.code == "PLUGIN_DEPENDENCY_ERROR"
        print("✓ PluginDependencyException 正常")
    
    return True


def test_plugin_repr():
    """测试9: 插件字符串表示"""
    print("\n" + "=" * 60)
    print("测试9: 插件字符串表示")
    print("=" * 60)
    
    plugin = TestPluginA()
    repr_str = repr(plugin)
    assert "test_plugin_a" in repr_str, "名称不在repr中"
    assert "1.0.0" in repr_str, "版本不在repr中"
    assert "unloaded" in repr_str, "状态不在repr中"
    print(f"✓ 插件repr正确: {repr_str}")
    
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("阶段46验证 - 插件系统")
    print("=" * 60)
    
    all_passed = True
    
    try:
        # 测试1: 初始化
        manager = test_plugin_system_initialization()
        
        # 测试2: 注册和加载
        test_plugin_registration_and_loading(manager)
        
        # 测试3: 启用/禁用
        test_plugin_enable_disable(manager)
        
        # 测试4: 钩子机制
        test_hook_mechanism(manager)
        
        # 测试5: 依赖管理
        test_plugin_dependency_management(manager)
        
        # 测试6: 元数据
        test_plugin_metadata()
        
        # 测试7: 状态枚举
        test_plugin_status_enum()
        
        # 测试8: 异常
        test_plugin_exceptions()
        
        # 测试9: repr
        test_plugin_repr()
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        all_passed = False
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有测试通过！")
        print("=" * 60)
        return 0
    else:
        print("✗ 测试未通过")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
