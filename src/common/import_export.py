"""
导入导出系统模块
遵循第一性原理：数据交换与格式转换

核心功能：
1. 数据导入
2. 数据导出
3. 格式转换
4. 批量处理
"""

from __future__ import annotations

import csv
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from common.utils import setup_logger

logger = setup_logger(__name__)


class ImportExportError(Exception):
    """导入导出异常"""
    def __init__(self, message: str, code: str = "IMPORT_EXPORT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class FormatNotSupportedError(ImportExportError):
    """格式不支持异常"""
    def __init__(self, fmt: str):
        super().__init__(f"不支持的格式: {fmt}", code="FORMAT_NOT_SUPPORTED")


class DataFormat(Enum):
    """数据格式"""
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    XML = "xml"


class DataAdapter(ABC):
    """数据适配器基类"""

    @abstractmethod
    def read(self, source: Union[str, bytes, Path]) -> List[Dict[str, Any]]:
        """读取数据"""
        pass

    @abstractmethod
    def write(self, data: List[Dict[str, Any]], target: Optional[Union[str, Path]] = None) -> Union[str, bytes]:
        """写入数据"""
        pass


class JSONAdapter(DataAdapter):
    """JSON数据适配器"""

    def read(self, source: Union[str, bytes, Path]) -> List[Dict[str, Any]]:
        if isinstance(source, Path):
            with open(source, "r", encoding="utf-8") as f:
                content = f.read()
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return [parsed]
        return parsed

    def write(self, data: List[Dict[str, Any]], target: Optional[Union[str, Path]] = None) -> Union[str, bytes]:
        output = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        if target:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(output)
        return output


class CSVAdapter(DataAdapter):
    """CSV数据适配器"""

    def read(self, source: Union[str, bytes, Path]) -> List[Dict[str, Any]]:
        if isinstance(source, Path):
            with open(source, "r", encoding="utf-8", newline="") as f:
                content = f.read()
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source
        reader = csv.DictReader(StringIO(content))
        return [row for row in reader]

    def write(self, data: List[Dict[str, Any]], target: Optional[Union[str, Path]] = None) -> Union[str, bytes]:
        if not data:
            output = ""
            if target:
                Path(target).write_text(output, encoding="utf-8")
            return output
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
        result = output.getvalue()
        if target:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(result)
        return result


class YAMLAdapter(DataAdapter):
    """YAML数据适配器"""

    def read(self, source: Union[str, bytes, Path]) -> List[Dict[str, Any]]:
        import yaml
        if isinstance(source, Path):
            with open(source, "r", encoding="utf-8") as f:
                content = f.read()
        elif isinstance(source, bytes):
            content = source.decode("utf-8")
        else:
            content = source
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return parsed
        return []

    def write(self, data: List[Dict[str, Any]], target: Optional[Union[str, Path]] = None) -> Union[str, bytes]:
        import yaml
        output = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        if target:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(output)
        return output


class AdapterRegistry:
    """适配器注册中心"""

    def __init__(self):
        self._adapters: Dict[str, DataAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("json", JSONAdapter())
        self.register("csv", CSVAdapter())
        self.register("yaml", YAMLAdapter())
        self.register("yml", YAMLAdapter())

    def register(self, fmt: str, adapter: DataAdapter) -> None:
        self._adapters[fmt.lower()] = adapter

    def get(self, fmt: str) -> DataAdapter:
        adapter = self._adapters.get(fmt.lower())
        if not adapter:
            raise FormatNotSupportedError(fmt)
        return adapter

    def supported_formats(self) -> List[str]:
        return list(self._adapters.keys())


@dataclass
class ImportJob:
    """导入任务"""
    source: Union[str, bytes, Path]
    source_format: str
    target_format: Optional[str] = None
    transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    batch_size: int = 100


@dataclass
class ExportJob:
    """导出任务"""
    data: List[Dict[str, Any]]
    target_format: str
    target: Optional[Union[str, Path]] = None
    transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


@dataclass
class JobResult:
    """任务结果"""
    success: bool
    record_count: int = 0
    output: Any = None
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class ImportExportEngine:
    """
    导入导出引擎

    核心功能：
    - 数据导入
    - 数据导出
    - 格式转换
    - 批量处理
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
        self._adapters = AdapterRegistry()
        self._initialized = True
        logger.info("导入导出引擎初始化完成")

    def import_data(self, job: ImportJob) -> JobResult:
        """导入数据"""
        import time
        start = time.time()
        errors = []
        records = []

        try:
            adapter = self._adapters.get(job.source_format)
            raw_data = adapter.read(job.source)

            for record in raw_data:
                try:
                    if job.transform:
                        record = job.transform(record)
                    records.append(record)
                except Exception as e:
                    errors.append(f"转换失败: {e}")

            # 格式转换
            if job.target_format and job.target_format != job.source_format:
                target_adapter = self._adapters.get(job.target_format)
                output = target_adapter.write(records)
            else:
                output = records

            duration = (time.time() - start) * 1000
            logger.info(f"导入完成: {len(records)} 条记录，耗时 {duration:.2f}ms")
            return JobResult(
                success=len(errors) == 0 or len(records) > 0,
                record_count=len(records),
                output=output,
                errors=errors,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"导入失败: {e}")
            return JobResult(
                success=False,
                record_count=0,
                errors=[str(e)],
                duration_ms=duration,
            )

    def export_data(self, job: ExportJob) -> JobResult:
        """导出数据"""
        import time
        start = time.time()
        errors = []

        try:
            records = []
            for record in job.data:
                try:
                    if job.transform:
                        record = job.transform(record)
                    records.append(record)
                except Exception as e:
                    errors.append(f"转换失败: {e}")

            adapter = self._adapters.get(job.target_format)
            output = adapter.write(records, job.target)

            duration = (time.time() - start) * 1000
            logger.info(f"导出完成: {len(records)} 条记录，耗时 {duration:.2f}ms")
            return JobResult(
                success=True,
                record_count=len(records),
                output=output,
                errors=errors,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"导出失败: {e}")
            return JobResult(
                success=False,
                record_count=0,
                errors=[str(e)],
                duration_ms=duration,
            )

    def convert(self, data: List[Dict[str, Any]], from_fmt: str, to_fmt: str) -> Any:
        """格式转换"""
        from_adapter = self._adapters.get(from_fmt)
        to_adapter = self._adapters.get(to_fmt)

        # 先序列化再读取，模拟跨格式转换
        serialized = from_adapter.write(data)
        if isinstance(serialized, bytes):
            return to_adapter.write(data)
        # 对于同类型直接转换
        return to_adapter.write(data)

    def batch_import(self, jobs: List[ImportJob]) -> List[JobResult]:
        """批量导入"""
        results = []
        for job in jobs:
            results.append(self.import_data(job))
        return results

    def batch_export(self, jobs: List[ExportJob]) -> List[JobResult]:
        """批量导出"""
        results = []
        for job in jobs:
            results.append(self.export_data(job))
        return results

    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        return self._adapters.supported_formats()


def demo_import_export():
    """演示导入导出系统"""
    print("=" * 60)
    print("导入导出系统演示")
    print("=" * 60)
    print()

    engine = ImportExportEngine()

    print("1. 支持的格式:")
    formats = engine.get_supported_formats()
    print(f"   ✓ {formats}")
    print()

    print("2. JSON导入:")
    json_data = '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]'
    job = ImportJob(source=json_data, source_format="json")
    result = engine.import_data(job)
    print(f"   ✓ 导入 {result.record_count} 条记录")
    print()

    print("3. CSV导出:")
    export_job = ExportJob(data=result.output, target_format="csv")
    export_result = engine.export_data(export_job)
    print(f"   ✓ CSV输出:\n{export_result.output}")
    print()

    print("4. 数据转换:")
    converted = engine.convert(result.output, "json", "yaml")
    print(f"   ✓ YAML输出:\n{converted}")
    print()

    print("5. 批量处理:")
    jobs = [
        ImportJob(source='[{"id": 1}]', source_format="json"),
        ImportJob(source='[{"id": 2}]', source_format="json"),
    ]
    batch_results = engine.batch_import(jobs)
    print(f"   ✓ 批量导入 {len(batch_results)} 个任务")
    print()

    print("6. 带转换的导入:")
    def upper_name(record):
        if "name" in record:
            record["name"] = record["name"].upper()
        return record

    transform_job = ImportJob(
        source='[{"name": "alice", "age": 20}]',
        source_format="json",
        transform=upper_name,
    )
    transform_result = engine.import_data(transform_job)
    print(f"   ✓ 转换后: {transform_result.output}")
    print()

    print("=" * 60)
    print("导入导出系统演示完成")
    print("=" * 60)
    print()
    print("✓ 数据导入")
    print("✓ 数据导出")
    print("✓ 格式转换")
    print("✓ 批量处理")
    print()


if __name__ == "__main__":
    demo_import_export()
