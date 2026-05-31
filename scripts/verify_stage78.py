"""
阶段78验证脚本：导入导出系统模块
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.import_export import (
    CSVAdapter,
    ExportJob,
    FormatNotSupportedError,
    ImportExportEngine,
    ImportJob,
    JSONAdapter,
    YAMLAdapter,
)


def test_json_adapter():
    """测试JSON适配器"""
    adapter = JSONAdapter()
    data = [{"name": "Alice", "age": "30"}]
    serialized = adapter.write(data)
    deserialized = adapter.read(serialized)
    assert deserialized == data
    print("✓ JSON适配器测试通过")


def test_csv_adapter():
    """测试CSV适配器"""
    adapter = CSVAdapter()
    data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    serialized = adapter.write(data)
    deserialized = adapter.read(serialized)
    assert len(deserialized) == 2
    assert deserialized[0]["name"] == "Alice"
    print("✓ CSV适配器测试通过")


def test_yaml_adapter():
    """测试YAML适配器"""
    adapter = YAMLAdapter()
    data = [{"name": "Alice", "age": 30}]
    serialized = adapter.write(data)
    deserialized = adapter.read(serialized)
    assert len(deserialized) == 1
    assert deserialized[0]["name"] == "Alice"
    print("✓ YAML适配器测试通过")


def test_import_json():
    """测试JSON导入"""
    engine = ImportExportEngine()
    job = ImportJob(source='[{"id": 1, "name": "test"}]', source_format="json")
    result = engine.import_data(job)
    assert result.success is True
    assert result.record_count == 1
    assert result.output[0]["name"] == "test"
    print("✓ JSON导入测试通过")


def test_export_csv():
    """测试CSV导出"""
    engine = ImportExportEngine()
    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    job = ExportJob(data=data, target_format="csv")
    result = engine.export_data(job)
    assert result.success is True
    assert "Alice" in result.output
    assert "Bob" in result.output
    print("✓ CSV导出测试通过")


def test_format_conversion():
    """测试格式转换"""
    engine = ImportExportEngine()
    data = [{"name": "Alice", "age": 30}]
    converted = engine.convert(data, "json", "yaml")
    assert "Alice" in converted
    print("✓ 格式转换测试通过")


def test_batch_import():
    """测试批量导入"""
    engine = ImportExportEngine()
    jobs = [
        ImportJob(source='[{"id": 1}]', source_format="json"),
        ImportJob(source='[{"id": 2}]', source_format="json"),
        ImportJob(source='[{"id": 3}]', source_format="json"),
    ]
    results = engine.batch_import(jobs)
    assert len(results) == 3
    assert all(r.success for r in results)
    assert sum(r.record_count for r in results) == 3
    print("✓ 批量导入测试通过")


def test_transform():
    """测试数据转换"""
    engine = ImportExportEngine()

    def add_tag(record):
        record["tag"] = "imported"
        return record

    job = ImportJob(
        source='[{"name": "Alice"}]',
        source_format="json",
        transform=add_tag,
    )
    result = engine.import_data(job)
    assert result.output[0]["tag"] == "imported"
    print("✓ 数据转换测试通过")


def test_unsupported_format():
    """测试不支持的格式"""
    engine = ImportExportEngine()
    job = ImportJob(source="", source_format="xml")
    result = engine.import_data(job)
    assert result.success is False
    assert any("不支持的格式" in e for e in result.errors)
    print("✓ 不支持格式异常测试通过")


def test_file_io():
    """测试文件读写"""
    adapter = JSONAdapter()
    data = [{"key": "value"}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        path = Path(f.name)
    try:
        adapter.write(data, path)
        read_data = adapter.read(path)
        assert read_data == data
    finally:
        path.unlink(missing_ok=True)
    print("✓ 文件IO测试通过")


def main():
    print("=" * 60)
    print("阶段78验证：导入导出系统模块")
    print("=" * 60)

    test_json_adapter()
    test_csv_adapter()
    test_yaml_adapter()
    test_import_json()
    test_export_csv()
    test_format_conversion()
    test_batch_import()
    test_transform()
    test_unsupported_format()
    test_file_io()

    print("=" * 60)
    print("阶段78验证全部通过 ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
