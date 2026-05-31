"""
数据流水线模块
遵循第一性原理：数据流的可组合性与可观测性

核心功能：
1. ETL流水线 - 抽取(Extract)/转换(Transform)/加载(Load)
2. 数据转换 - 链式数据处理器
3. 数据验证 - 输入/中间/输出数据校验
4. 流水线编排 - 阶段管理与依赖执行
"""

from __future__ import annotations

import time
import traceback
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from common.utils import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


class PipelineStatus(Enum):
    """流水线状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(Enum):
    """阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.valid and not self.errors


class DataValidator(ABC):
    """数据验证器抽象基类"""

    @abstractmethod
    def validate(self, data: Any) -> ValidationResult:
        pass


class TypeValidator(DataValidator):
    """类型验证器"""

    def __init__(self, expected_type: type):
        self.expected_type = expected_type

    def validate(self, data: Any) -> ValidationResult:
        if not isinstance(data, self.expected_type):
            return ValidationResult(
                valid=False,
                errors=[f"类型错误：期望 {self.expected_type.__name__}，实际 {type(data).__name__}"],
            )
        return ValidationResult(valid=True)


class RangeValidator(DataValidator):
    """范围验证器（用于数值）"""

    def __init__(self, min_value: Optional[float] = None, max_value: Optional[float] = None):
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, data: Any) -> ValidationResult:
        errors = []
        if self.min_value is not None and data < self.min_value:
            errors.append(f"值 {data} 小于最小值 {self.min_value}")
        if self.max_value is not None and data > self.max_value:
            errors.append(f"值 {data} 大于最大值 {self.max_value}")
        return ValidationResult(valid=len(errors) == 0, errors=errors)


class NotNullValidator(DataValidator):
    """非空验证器"""

    def validate(self, data: Any) -> ValidationResult:
        if data is None:
            return ValidationResult(valid=False, errors=["数据不能为空"])
        if isinstance(data, (list, dict, str)) and len(data) == 0:
            return ValidationResult(valid=False, errors=["数据不能为空集合"])
        return ValidationResult(valid=True)


class CustomValidator(DataValidator):
    """自定义验证器"""

    def __init__(self, validator_fn: Callable[[Any], ValidationResult]):
        self.validator_fn = validator_fn

    def validate(self, data: Any) -> ValidationResult:
        return self.validator_fn(data)


class DataTransformer(ABC):
    """数据转换器抽象基类"""

    @abstractmethod
    def transform(self, data: Any) -> Any:
        pass

    def __or__(self, other: DataTransformer) -> ChainedTransformer:
        return ChainedTransformer([self, other])


class ChainedTransformer(DataTransformer):
    """链式转换器"""

    def __init__(self, transformers: List[DataTransformer]):
        self.transformers = transformers

    def transform(self, data: Any) -> Any:
        for t in self.transformers:
            data = t.transform(data)
        return data

    def __or__(self, other: DataTransformer) -> ChainedTransformer:
        return ChainedTransformer(self.transformers + [other])


class FunctionTransformer(DataTransformer):
    """函数转换器"""

    def __init__(self, fn: Callable[[Any], Any], name: str = ""):
        self.fn = fn
        self.name = name or fn.__name__

    def transform(self, data: Any) -> Any:
        return self.fn(data)


class FilterTransformer(DataTransformer):
    """过滤转换器"""

    def __init__(self, predicate: Callable[[Any], bool]):
        self.predicate = predicate

    def transform(self, data: Any) -> Any:
        if isinstance(data, list):
            return [item for item in data if self.predicate(item)]
        return data if self.predicate(data) else None


class MapTransformer(DataTransformer):
    """映射转换器"""

    def __init__(self, mapper: Callable[[Any], Any]):
        self.mapper = mapper

    def transform(self, data: Any) -> Any:
        if isinstance(data, list):
            return [self.mapper(item) for item in data]
        return self.mapper(data)


@dataclass
class StageResult:
    """阶段执行结果"""
    stage_name: str
    status: StageStatus
    input_data: Any = None
    output_data: Any = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    stage_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class PipelineStage(ABC):
    """流水线阶段抽象基类"""

    def __init__(
        self,
        name: str,
        input_validators: Optional[List[DataValidator]] = None,
        output_validators: Optional[List[DataValidator]] = None,
    ):
        self.name = name
        self.input_validators = input_validators or []
        self.output_validators = output_validators or []
        self.dependencies: List[str] = []

    def add_dependency(self, stage_name: str) -> PipelineStage:
        self.dependencies.append(stage_name)
        return self

    def validate_input(self, data: Any) -> ValidationResult:
        errors = []
        warnings = []
        for validator in self.input_validators:
            result = validator.validate(data)
            if not result.valid:
                errors.extend(result.errors)
            warnings.extend(result.warnings)
        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_output(self, data: Any) -> ValidationResult:
        errors = []
        warnings = []
        for validator in self.output_validators:
            result = validator.validate(data)
            if not result.valid:
                errors.extend(result.errors)
            warnings.extend(result.warnings)
        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    @abstractmethod
    def execute(self, data: Any, context: Dict[str, Any]) -> Any:
        pass

    def run(self, data: Any, context: Dict[str, Any]) -> StageResult:
        start = time.time()
        stage_result = StageResult(stage_name=self.name, input_data=data, status=StageStatus.RUNNING)

        # 输入验证
        input_validation = self.validate_input(data)
        if not input_validation.ok:
            stage_result.status = StageStatus.FAILED
            stage_result.error = f"输入验证失败: {input_validation.errors}"
            stage_result.duration_ms = (time.time() - start) * 1000
            logger.error(f"阶段 [{self.name}] 输入验证失败: {input_validation.errors}")
            return stage_result

        try:
            output = self.execute(data, context)
        except Exception as e:
            stage_result.status = StageStatus.FAILED
            stage_result.error = f"{e}\n{traceback.format_exc()}"
            stage_result.duration_ms = (time.time() - start) * 1000
            logger.error(f"阶段 [{self.name}] 执行异常: {e}")
            return stage_result

        # 输出验证
        output_validation = self.validate_output(output)
        if not output_validation.ok:
            stage_result.status = StageStatus.FAILED
            stage_result.error = f"输出验证失败: {output_validation.errors}"
            stage_result.duration_ms = (time.time() - start) * 1000
            logger.error(f"阶段 [{self.name}] 输出验证失败: {output_validation.errors}")
            return stage_result

        stage_result.output_data = output
        stage_result.status = StageStatus.SUCCESS
        stage_result.duration_ms = (time.time() - start) * 1000
        logger.info(f"阶段 [{self.name}] 执行成功，耗时 {stage_result.duration_ms:.2f}ms")
        return stage_result


class TransformStage(PipelineStage):
    """转换阶段"""

    def __init__(
        self,
        name: str,
        transformer: DataTransformer,
        input_validators: Optional[List[DataValidator]] = None,
        output_validators: Optional[List[DataValidator]] = None,
    ):
        super().__init__(name, input_validators, output_validators)
        self.transformer = transformer

    def execute(self, data: Any, context: Dict[str, Any]) -> Any:
        return self.transformer.transform(data)


class FunctionStage(PipelineStage):
    """函数执行阶段"""

    def __init__(
        self,
        name: str,
        fn: Callable[[Any, Dict[str, Any]], Any],
        input_validators: Optional[List[DataValidator]] = None,
        output_validators: Optional[List[DataValidator]] = None,
    ):
        super().__init__(name, input_validators, output_validators)
        self.fn = fn

    def execute(self, data: Any, context: Dict[str, Any]) -> Any:
        return self.fn(data, context)


@dataclass
class PipelineResult:
    """流水线执行结果"""
    pipeline_id: str
    status: PipelineStatus
    stage_results: List[StageResult] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def output(self) -> Any:
        if self.stage_results and self.stage_results[-1].status == StageStatus.SUCCESS:
            return self.stage_results[-1].output_data
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "stages": [s.to_dict() for s in self.stage_results],
        }


class DataPipeline:
    """数据流水线 - ETL编排引擎"""

    def __init__(self, name: str = "", pipeline_id: str = ""):
        self.name = name or f"pipeline_{uuid.uuid4().hex[:8]}"
        self.pipeline_id = pipeline_id or str(uuid.uuid4())
        self.stages: List[PipelineStage] = []
        self._stage_map: Dict[str, PipelineStage] = {}
        self._context: Dict[str, Any] = {}

    def add_stage(self, stage: PipelineStage) -> DataPipeline:
        """添加阶段"""
        self.stages.append(stage)
        self._stage_map[stage.name] = stage
        return self

    def set_context(self, key: str, value: Any) -> DataPipeline:
        """设置上下文"""
        self._context[key] = value
        return self

    def run(self, initial_data: Any) -> PipelineResult:
        """运行流水线"""
        result = PipelineResult(
            pipeline_id=self.pipeline_id,
            status=PipelineStatus.RUNNING,
            context=self._context.copy(),
            start_time=time.time(),
        )

        current_data = initial_data
        executed_stages: set = set()

        for stage in self.stages:
            # 检查依赖
            deps_satisfied = all(dep in executed_stages for dep in stage.dependencies)
            if not deps_satisfied:
                missing = [dep for dep in stage.dependencies if dep not in executed_stages]
                stage_result = StageResult(
                    stage_name=stage.name,
                    status=StageStatus.SKIPPED,
                    error=f"依赖未满足: {missing}",
                )
                result.stage_results.append(stage_result)
                continue

            stage_result = stage.run(current_data, result.context)
            result.stage_results.append(stage_result)
            executed_stages.add(stage.name)

            if stage_result.status == StageStatus.SUCCESS:
                current_data = stage_result.output_data
                result.context[f"stage.{stage.name}.output"] = current_data
            elif stage_result.status == StageStatus.FAILED:
                result.status = PipelineStatus.FAILED
                result.end_time = time.time()
                logger.error(f"流水线 [{self.name}] 在阶段 [{stage.name}] 失败")
                return result

        result.status = PipelineStatus.SUCCESS
        result.end_time = time.time()
        logger.info(f"流水线 [{self.name}] 执行成功，总耗时 {result.duration_ms:.2f}ms")
        return result

    def run_with_error_handling(self, initial_data: Any, on_error: str = "stop") -> PipelineResult:
        """带错误处理的运行"""
        result = self.run(initial_data)
        if result.status == PipelineStatus.FAILED and on_error == "continue":
            result.status = PipelineStatus.SUCCESS
            logger.warning(f"流水线 [{self.name}] 错误被忽略，继续执行")
        return result

    def get_stage(self, name: str) -> Optional[PipelineStage]:
        """获取阶段"""
        return self._stage_map.get(name)

    def reset(self) -> None:
        """重置流水线"""
        self.stages.clear()
        self._stage_map.clear()
        self._context.clear()


# 便捷构建函数
def extract_stage(name: str = "extract", fn: Optional[Callable[[Any, Dict], Any]] = None) -> FunctionStage:
    """创建抽取阶段"""
    return FunctionStage(name, fn or (lambda data, ctx: data))


def transform_stage(
    name: str = "transform",
    transformer: Optional[DataTransformer] = None,
) -> TransformStage:
    """创建转换阶段"""
    return TransformStage(name, transformer or FunctionTransformer(lambda x: x))


def load_stage(name: str = "load", fn: Optional[Callable[[Any, Dict], Any]] = None) -> FunctionStage:
    """创建加载阶段"""
    return FunctionStage(name, fn or (lambda data, ctx: data))
