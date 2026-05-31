#!/usr/bin/env python3
"""
阶段45验证脚本：监控告警系统集成

验收标准：
1. 监控系统正常初始化
2. 指标收集器正常工作
3. 告警通道正常工作
4. 告警规则正常触发
5. 告警管理功能正常
6. 告警历史记录正常
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.common.monitoring import (
    MonitoringSystem, MetricsCollector, AlertManager, AlertRule,
    AlertSeverity, AlertStatus, ConsoleAlertChannel, LogAlertChannel
)

def test_monitoring_system_initialization():
    """测试监控系统初始化"""
    print("\n=== 验收标准1: 监控系统正常初始化 ===")
    
    try:
        system = MonitoringSystem(name="test_monitoring")
        print(f"✅ 监控系统初始化成功: {system.name}")
        print(f"   - 收集器: {system.collector.name}")
        print(f"   - 告警管理器: {system.alert_manager.name}")
        return True
    except Exception as e:
        print(f"❌ 监控系统初始化失败: {e}")
        return False

def test_metrics_collector():
    """测试指标收集器"""
    print("\n=== 验收标准2: 指标收集器正常工作 ===")
    
    try:
        collector = MetricsCollector("test_collector")
        
        collector.record_counter("requests_total", 1.0)
        collector.record_counter("requests_total", 2.0)
        collector.record_gauge("cpu_usage", 75.5)
        collector.record_histogram("response_time", 0.123)
        
        metrics = collector.get_all_metrics()
        print(f"✅ 记录了 {len(metrics)} 个指标")
        
        for metric in metrics:
            print(f"   - {metric.name}: {metric.value}")
        
        return True
    except Exception as e:
        print(f"❌ 指标收集器测试失败: {e}")
        return False

def test_alert_channels():
    """测试告警通道"""
    print("\n=== 验收标准3: 告警通道正常工作 ===")
    
    try:
        console_channel = ConsoleAlertChannel()
        log_channel = LogAlertChannel()
        
        from src.common.monitoring import Alert
        
        alert = Alert(
            alert_id="test_001",
            name="Test Alert",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.FIRING,
            message="测试告警消息",
            metric_name="test_metric",
            current_value=90.0,
            threshold=80.0
        )
        
        console_channel.send(alert)
        log_channel.send(alert)
        
        print(f"✅ 告警通道正常工作")
        print(f"   - 控制台收到 {len(console_channel.get_alerts())} 个告警")
        
        return True
    except Exception as e:
        print(f"❌ 告警通道测试失败: {e}")
        return False

def test_alert_rules():
    """测试告警规则触发"""
    print("\n=== 验收标准4: 告警规则正常触发 ===")
    
    try:
        system = MonitoringSystem("test_system")
        
        system.add_alert_rule(
            name="High CPU Usage",
            metric_name="cpu_usage",
            condition=">",
            threshold=80.0,
            severity=AlertSeverity.HIGH,
            description="CPU使用率超过80%"
        )
        
        system.record_gauge("cpu_usage", 85.0)
        
        alerts = system.check_alerts()
        
        print(f"✅ 告警规则触发成功")
        print(f"   - 触发告警数: {len(alerts)}")
        
        if alerts:
            for alert in alerts:
                print(f"   - 告警: {alert.name} - {alert.message}")
        
        return True
    except Exception as e:
        print(f"❌ 告警规则测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alert_management():
    """测试告警管理功能"""
    print("\n=== 验收标准5: 告警管理功能正常 ===")
    
    try:
        system = MonitoringSystem("test_system")
        
        console_channel = ConsoleAlertChannel()
        system.alert_manager.add_channel(console_channel, "test_console")
        
        system.add_alert_rule(
            name="Test Rule",
            metric_name="test_metric",
            condition=">",
            threshold=50.0,
            severity=AlertSeverity.MEDIUM,
            description="测试规则"
        )
        
        system.record_gauge("test_metric", 75.0)
        alerts = system.check_alerts()
        
        if alerts:
            alert = alerts[0]
            print(f"✅ 告警管理功能正常")
            print(f"   - 告警ID: {alert.alert_id}")
            print(f"   - 状态: {alert.status.value}")
            
            system.alert_manager.acknowledge_alert(alert.alert_id)
            print(f"   - 确认后状态: {alert.status.value}")
            
            system.alert_manager.resolve_alert(alert.alert_id)
            print(f"   - 解决后状态: {alert.status.value}")
        
        return True
    except Exception as e:
        print(f"❌ 告警管理测试失败: {e}")
        return False

def test_alert_history():
    """测试告警历史记录"""
    print("\n=== 验收标准6: 告警历史记录正常 ===")
    
    try:
        system = MonitoringSystem("test_system")
        
        console_channel = ConsoleAlertChannel()
        system.alert_manager.add_channel(console_channel, "test_console")
        
        system.add_alert_rule(
            name="History Test",
            metric_name="metric_for_history",
            condition=">",
            threshold=30.0,
            severity=AlertSeverity.LOW,
            description="历史记录测试"
        )
        
        system.record_gauge("metric_for_history", 50.0)
        system.check_alerts()
        
        history = system.alert_manager.get_alert_history()
        
        print(f"✅ 告警历史记录正常")
        print(f"   - 历史记录数: {len(history)}")
        
        if history:
            print(f"   - 最新告警: {history[-1].name}")
        
        return True
    except Exception as e:
        print(f"❌ 告警历史测试失败: {e}")
        return False

def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段45验证：监控告警系统集成")
    print("=" * 60)
    
    results = []
    
    results.append(("监控系统初始化", test_monitoring_system_initialization()))
    results.append(("指标收集器", test_metrics_collector()))
    results.append(("告警通道", test_alert_channels()))
    results.append(("告警规则触发", test_alert_rules()))
    results.append(("告警管理功能", test_alert_management()))
    results.append(("告警历史记录", test_alert_history()))
    
    print("\n" + "=" * 60)
    print("验收结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 阶段45验收通过！")
        return 0
    else:
        print("\n❌ 阶段45验收未通过！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
