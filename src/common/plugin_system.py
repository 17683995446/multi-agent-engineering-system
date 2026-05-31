"""
公共层 - 插件系统模块
职责：提供动态插件加载、生命周期管理、钩子机制和依赖管理
依赖规则：仅依赖公共层 utils
遵循第一性原理：
- 插件是独立的功能单元（原子性）
- 钩子是可组合的扩展点（组合性）
- 依赖关系构成有向无环图（DAG）
"""

import abc
import importlib
import importlib.util
import inspect
import logging
import pkgutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar

from .utils import setup_logger, SystemException


class PluginException(SystemException):
    """插件异常"""
    def __init__(self, message: str, trace_id: Optional[str] = None):
        super().__init__(message, code="PLUGIN_ERROR", trace_id=trace_id)


class PluginDependencyException(PluginException):
    """插件依赖异常"""
    def __init__(self, message: str, trace_id: Optional[str] = None):
        super().__init__(message, trace_id=trace_id)
        self.code = "PLUGIN_DEPENDENCY_ERROR"


class HookException(PluginException):
    """钩子异常"""
    def __init__(self, message: str, trace_id: Optional[str] = None):
        super().__init__(message, trace_id=trace_id)
        self.code = "HOOK_ERROR"


class PluginStatus(Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    REGISTERED = "registered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    priority: int = 0


class PluginBase(abc.ABC):
    """
    插件基类 - 所有插件必须继承此类
    
    遵循第一性原理：
    - 每个插件是独立的功能原子单元
    - 插件通过声明式接口与系统交互
    - 生命周期由系统统一管理
    """
    
    metadata: PluginMetadata = PluginMetadata(name="base")
    
    def __init__(self):
        self._status = PluginStatus.UNLOADED
        self._logger = setup_logger(f"plugin.{self.metadata.name}")
        self._context: Dict[str, Any] = {}
    
    @property
    def status(self) -> PluginStatus:
        return self._status
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def version(self) -> str:
        return self.metadata.version
    
    @property
    def dependencies(self) -> List[str]:
        return list(self.metadata.dependencies)
    
    def set_context(self, key: str, value: Any):
        """设置插件上下文"""
        self._context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取插件上下文"""
        return self._context.get(key, default)
    
    def initialize(self) -> bool:
        """
        初始化插件 - 子类可重写
        返回: 是否初始化成功
        """
        self._status = PluginStatus.LOADED
        self._logger.info(f"Plugin {self.name} initialized")
        return True
    
    def startup(self) -> bool:
        """
        启动插件 - 子类可重写
        返回: 是否启动成功
        """
        self._status = PluginStatus.ENABLED
        self._logger.info(f"Plugin {self.name} started")
        return True
    
    def shutdown(self) -> bool:
        """
        关闭插件 - 子类可重写
        返回: 是否关闭成功
        """
        self._status = PluginStatus.DISABLED
        self._logger.info(f"Plugin {self.name} shutdown")
        return True
    
    def on_enable(self):
        """插件启用回调"""
        pass
    
    def on_disable(self):
        """插件禁用回调"""
        pass
    
    def __repr__(self) -> str:
        return f"<Plugin {self.name}@{self.version} status={self._status.value}>"


T = TypeVar("T", bound=PluginBase)


class HookManager:
    """
    钩子管理器 - 允许插件扩展系统功能
    
    遵循第一性原理：
    - 钩子是系统预留的扩展点
    - 多个插件可注册同一钩子，按优先级执行
    - 钩子执行结果可链式传递
    """
    
    def __init__(self):
        self._hooks: Dict[str, List[Dict[str, Any]]] = {}
        self._logger = setup_logger("hook_manager")
    
    def register_hook(self, hook_name: str, callback: Callable, priority: int = 0, plugin_name: Optional[str] = None):
        """
        注册钩子回调
        
        Args:
            hook_name: 钩子名称
            callback: 回调函数
            priority: 优先级，数值越小优先级越高
            plugin_name: 注册钩子的插件名称
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        
        hook_info = {
            "callback": callback,
            "priority": priority,
            "plugin_name": plugin_name or "unknown"
        }
        self._hooks[hook_name].append(hook_info)
        self._hooks[hook_name].sort(key=lambda x: x["priority"])
        self._logger.debug(f"Registered hook '{hook_name}' from plugin '{plugin_name}' with priority {priority}")
    
    def unregister_hook(self, hook_name: Optional[str] = None, callback: Optional[Callable] = None, plugin_name: Optional[str] = None):
        """
        注销钩子回调
        
        Args:
            hook_name: 钩子名称，为None则匹配所有钩子
            callback: 要注销的回调函数，为None则忽略
            plugin_name: 要注销的插件名称，为None则忽略
        """
        if hook_name is not None:
            if hook_name not in self._hooks:
                return
            
            if callback is None and plugin_name is None:
                del self._hooks[hook_name]
                return
            
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name]
                if not (
                    (callback is not None and h["callback"] == callback) or
                    (plugin_name is not None and h["plugin_name"] == plugin_name)
                )
            ]
            
            if not self._hooks[hook_name]:
                del self._hooks[hook_name]
        else:
            # hook_name 为 None，遍历所有钩子按 plugin_name 注销
            if plugin_name is None and callback is None:
                return
            
            for hname in list(self._hooks.keys()):
                self._hooks[hname] = [
                    h for h in self._hooks[hname]
                    if not (
                        (callback is not None and h["callback"] == callback) or
                        (plugin_name is not None and h["plugin_name"] == plugin_name)
                    )
                ]
                if not self._hooks[hname]:
                    del self._hooks[hname]
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        执行钩子 - 调用所有注册的回调
        
        Args:
            hook_name: 钩子名称
            *args, **kwargs: 传递给回调函数的参数
            
        Returns:
            所有回调的返回结果列表
        """
        if hook_name not in self._hooks:
            return []
        
        results = []
        for hook_info in self._hooks[hook_name]:
            try:
                result = hook_info["callback"](*args, **kwargs)
                results.append(result)
            except Exception as e:
                self._logger.error(f"Hook '{hook_name}' execution failed for plugin '{hook_info['plugin_name']}': {e}")
                raise HookException(f"Hook '{hook_name}' execution failed: {e}")
        
        return results
    
    def execute_hook_chain(self, hook_name: str, initial_value: Any, *args, **kwargs) -> Any:
        """
        链式执行钩子 - 每个回调的返回值作为下一个回调的输入
        
        Args:
            hook_name: 钩子名称
            initial_value: 初始值
            *args, **kwargs: 额外参数
            
        Returns:
            最终处理后的值
        """
        if hook_name not in self._hooks:
            return initial_value
        
        value = initial_value
        for hook_info in self._hooks[hook_name]:
            try:
                value = hook_info["callback"](value, *args, **kwargs)
            except Exception as e:
                self._logger.error(f"Hook chain '{hook_name}' execution failed for plugin '{hook_info['plugin_name']}': {e}")
                raise HookException(f"Hook chain '{hook_name}' execution failed: {e}")
        
        return value
    
    def get_hook_callbacks(self, hook_name: str) -> List[Dict[str, Any]]:
        """获取钩子的所有回调信息"""
        return list(self._hooks.get(hook_name, []))
    
    def list_hooks(self) -> List[str]:
        """列出所有已注册的钩子名称"""
        return list(self._hooks.keys())
    
    def clear(self):
        """清除所有钩子"""
        self._hooks.clear()


class PluginRegistry:
    """
    插件注册表 - 管理所有已注册的插件
    
    遵循第一性原理：
    - 注册表是插件的唯一身份来源
    - 支持按名称、类型、状态查询
    - 保证插件名称唯一性
    """
    
    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_classes: Dict[str, Type[PluginBase]] = {}
        self._logger = setup_logger("plugin_registry")
    
    def register(self, plugin_class: Type[PluginBase]) -> bool:
        """
        注册插件类
        
        Args:
            plugin_class: 插件类（非实例）
            
        Returns:
            是否注册成功
        """
        if not issubclass(plugin_class, PluginBase):
            raise PluginException(f"Class {plugin_class.__name__} must inherit from PluginBase")
        
        name = plugin_class.metadata.name
        if name in self._plugin_classes:
            self._logger.warning(f"Plugin class '{name}' already registered, overwriting")
        
        self._plugin_classes[name] = plugin_class
        self._logger.info(f"Registered plugin class: {name}")
        return True
    
    def unregister(self, name: str) -> bool:
        """注销插件类"""
        if name in self._plugin_classes:
            del self._plugin_classes[name]
            self._logger.info(f"Unregistered plugin class: {name}")
            return True
        return False
    
    def add_instance(self, plugin: PluginBase) -> bool:
        """添加插件实例"""
        name = plugin.name
        if name in self._plugins:
            self._logger.warning(f"Plugin instance '{name}' already exists, overwriting")
        
        self._plugins[name] = plugin
        self._logger.info(f"Added plugin instance: {name}")
        return True
    
    def remove_instance(self, name: str) -> bool:
        """移除插件实例"""
        if name in self._plugins:
            del self._plugins[name]
            self._logger.info(f"Removed plugin instance: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[PluginBase]:
        """获取插件实例"""
        return self._plugins.get(name)
    
    def get_class(self, name: str) -> Optional[Type[PluginBase]]:
        """获取插件类"""
        return self._plugin_classes.get(name)
    
    def list_plugins(self) -> List[str]:
        """列出所有已注册插件名称"""
        return list(self._plugins.keys())
    
    def list_classes(self) -> List[str]:
        """列出所有已注册插件类名称"""
        return list(self._plugin_classes.keys())
    
    def get_by_status(self, status: PluginStatus) -> List[PluginBase]:
        """按状态获取插件实例"""
        return [p for p in self._plugins.values() if p.status == status]
    
    def clear(self):
        """清空注册表"""
        self._plugins.clear()
        self._plugin_classes.clear()


class PluginManager:
    """
    插件管理器 - 统一管理插件的加载、注册、启用、禁用和卸载
    
    遵循第一性原理：
    - 插件生命周期由管理器统一控制
    - 依赖关系在启用前自动解析
    - 钩子与插件解耦，通过HookManager桥接
    """
    
    def __init__(self):
        self._registry = PluginRegistry()
        self._hook_manager = HookManager()
        self._logger = setup_logger("plugin_manager")
        self._load_paths: List[Path] = []
    
    @property
    def registry(self) -> PluginRegistry:
        return self._registry
    
    @property
    def hook_manager(self) -> HookManager:
        return self._hook_manager
    
    def add_load_path(self, path: Path):
        """添加插件加载路径"""
        if path not in self._load_paths:
            self._load_paths.append(path)
            self._logger.info(f"Added plugin load path: {path}")
    
    def load_plugin(self, plugin_class: Type[PluginBase]) -> PluginBase:
        """
        加载单个插件类
        
        Args:
            plugin_class: 插件类
            
        Returns:
            插件实例
        """
        self._registry.register(plugin_class)
        instance = plugin_class()
        instance.initialize()
        instance._status = PluginStatus.REGISTERED
        self._registry.add_instance(instance)
        self._logger.info(f"Loaded plugin: {instance.name}")
        return instance
    
    def load_plugins_from_module(self, module_name: str) -> List[PluginBase]:
        """
        从模块加载所有插件
        
        Args:
            module_name: 模块名称
            
        Returns:
            加载的插件实例列表
        """
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise PluginException(f"Failed to import module {module_name}: {e}")
        
        plugins = []
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, PluginBase) and 
                obj is not PluginBase and
                not inspect.isabstract(obj)):
                try:
                    plugin = self.load_plugin(obj)
                    plugins.append(plugin)
                except Exception as e:
                    self._logger.error(f"Failed to load plugin {name}: {e}")
        
        return plugins
    
    def load_plugins_from_path(self, path: Path) -> List[PluginBase]:
        """
        从路径加载所有插件
        
        Args:
            path: 插件目录路径
            
        Returns:
            加载的插件实例列表
        """
        if not path.exists():
            raise PluginException(f"Plugin path does not exist: {path}")
        
        plugins = []
        for file_path in path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                continue
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginBase) and 
                    obj is not PluginBase and
                    not inspect.isabstract(obj)):
                    try:
                        plugin = self.load_plugin(obj)
                        plugins.append(plugin)
                    except Exception as e:
                        self._logger.error(f"Failed to load plugin {name} from {file_path}: {e}")
        
        return plugins
    
    def _resolve_dependencies(self, plugin: PluginBase, visited: Optional[Set[str]] = None, stack: Optional[List[str]] = None) -> List[str]:
        """
        解析插件依赖（拓扑排序）
        
        Args:
            plugin: 目标插件
            visited: 已访问的插件集合
            stack: 当前依赖栈（用于检测循环依赖）
            
        Returns:
            按启用顺序排列的依赖插件名称列表
        """
        if visited is None:
            visited = set()
        if stack is None:
            stack = []
        
        name = plugin.name
        if name in visited:
            return []
        
        if name in stack:
            cycle = " -> ".join(stack[stack.index(name):] + [name])
            raise PluginDependencyException(f"Circular dependency detected: {cycle}")
        
        stack.append(name)
        result = []
        
        for dep_name in plugin.dependencies:
            dep_plugin = self._registry.get(dep_name)
            if dep_plugin is None:
                dep_class = self._registry.get_class(dep_name)
                if dep_class is None:
                    raise PluginDependencyException(
                        f"Plugin '{name}' depends on '{dep_name}' which is not loaded"
                    )
                dep_plugin = self.load_plugin(dep_class)
            
            if dep_plugin.status != PluginStatus.ENABLED:
                result.extend(self._resolve_dependencies(dep_plugin, visited, stack))
                result.append(dep_name)
        
        stack.pop()
        visited.add(name)
        return result
    
    def enable_plugin(self, name: str) -> bool:
        """
        启用插件（自动解析并启用依赖）
        
        Args:
            name: 插件名称
            
        Returns:
            是否启用成功
        """
        plugin = self._registry.get(name)
        if plugin is None:
            raise PluginException(f"Plugin '{name}' not found")
        
        if plugin.status == PluginStatus.ENABLED:
            return True
        
        # 解析并启用依赖
        dependencies = self._resolve_dependencies(plugin)
        for dep_name in dependencies:
            dep_plugin = self._registry.get(dep_name)
            if dep_plugin and dep_plugin.status != PluginStatus.ENABLED:
                self._enable_single(dep_plugin)
        
        return self._enable_single(plugin)
    
    def _enable_single(self, plugin: PluginBase) -> bool:
        """启用单个插件（内部方法）"""
        try:
            plugin.startup()
            plugin.on_enable()
            plugin._status = PluginStatus.ENABLED
            self._logger.info(f"Enabled plugin: {plugin.name}")
            return True
        except Exception as e:
            plugin._status = PluginStatus.ERROR
            self._logger.error(f"Failed to enable plugin {plugin.name}: {e}")
            return False
    
    def disable_plugin(self, name: str) -> bool:
        """
        禁用插件
        
        Args:
            name: 插件名称
            
        Returns:
            是否禁用成功
        """
        plugin = self._registry.get(name)
        if plugin is None:
            raise PluginException(f"Plugin '{name}' not found")
        
        if plugin.status != PluginStatus.ENABLED:
            return True
        
        # 注销该插件注册的所有钩子
        self._hook_manager.unregister_hook(plugin_name=name)
        
        plugin.on_disable()
        plugin.shutdown()
        plugin._status = PluginStatus.DISABLED
        self._logger.info(f"Disabled plugin: {name}")
        return True
    
    def unload_plugin(self, name: str) -> bool:
        """
        卸载插件（先禁用再移除）
        
        Args:
            name: 插件名称
            
        Returns:
            是否卸载成功
        """
        plugin = self._registry.get(name)
        if plugin is None:
            return False
        
        if plugin.status == PluginStatus.ENABLED:
            self.disable_plugin(name)
        
        self._registry.remove_instance(name)
        self._registry.unregister(name)
        self._logger.info(f"Unloaded plugin: {name}")
        return True
    
    def enable_all(self) -> Dict[str, bool]:
        """启用所有已加载的插件"""
        results = {}
        for name in self._registry.list_plugins():
            try:
                results[name] = self.enable_plugin(name)
            except Exception as e:
                self._logger.error(f"Failed to enable plugin {name}: {e}")
                results[name] = False
        return results
    
    def disable_all(self) -> Dict[str, bool]:
        """禁用所有已启用的插件"""
        results = {}
        for plugin in self._registry.get_by_status(PluginStatus.ENABLED):
            results[plugin.name] = self.disable_plugin(plugin.name)
        return results
    
    def unload_all(self):
        """卸载所有插件"""
        self.disable_all()
        for name in list(self._registry.list_plugins()):
            self.unload_plugin(name)
        self._hook_manager.clear()
    
    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """获取插件实例"""
        return self._registry.get(name)
    
    def list_plugins(self) -> List[str]:
        """列出所有插件名称"""
        return self._registry.list_plugins()
    
    def list_enabled_plugins(self) -> List[str]:
        """列出所有已启用插件名称"""
        return [p.name for p in self._registry.get_by_status(PluginStatus.ENABLED)]
    
    def register_hook(self, hook_name: str, callback: Callable, priority: int = 0, plugin_name: Optional[str] = None):
        """注册钩子（代理到HookManager）"""
        self._hook_manager.register_hook(hook_name, callback, priority, plugin_name)
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """执行钩子（代理到HookManager）"""
        return self._hook_manager.execute_hook(hook_name, *args, **kwargs)
    
    def execute_hook_chain(self, hook_name: str, initial_value: Any, *args, **kwargs) -> Any:
        """链式执行钩子（代理到HookManager）"""
        return self._hook_manager.execute_hook_chain(hook_name, initial_value, *args, **kwargs)
