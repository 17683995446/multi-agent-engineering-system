#!/usr/bin/env python3
"""
阶段62验证脚本：数据流水线
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from common.data_pipeline import (
    DataPipeline,
    TransformStage,
    FunctionStage,
    FunctionTransformer,
    FilterTransformer,
    MapTransformer,
    ChainedTransformer,
    TypeValidator,
    RangeValidator,
    NotNullValidator,
    CustomValidator,
    ValidationResult,
    PipelineStatus,
    StageStatus,
    extract_stage,
    transform_stage,
    load_stage,
)


def test_validation_result():
    """测试验证结果"""
    vr = ValidationResult(valid=True)
    assert vr.ok is True

    vr2 = ValidationResult(valid=False, errors=["error1"])
    assert vr2.ok is False
    print("[PASS] Validation Result")


def test_type_validator():
    """测试类型验证器"""
    v = TypeValidator(int)
    assert v.validate(42).ok is True
    assert v.validate("42").ok is False
    print("[PASS] Type Validator")


def test_range_validator():
    """测试范围验证器"""
    v = RangeValidator(min_value=0, max_value=100)
    assert v.validate(50).ok is True
    assert v.validate(-1).ok is False
    assert v.validate(101).ok is False
    print("[PASS] Range Validator")


def test_not_null_validator():
    """测试非空验证器"""
    v = NotNullValidator()
    assert v.validate("hello").ok is True
    assert v.validate(None).ok is False
    assert v.validate([]).ok is False
    print("[PASS] NotNull Validator")


def test_custom_validator():
    """测试自定义验证器"""
    def check_even(data):
        if data % 2 != 0:
            return ValidationResult(valid=False, errors=["不是偶数"])
        return ValidationResult(valid=True)

    v = CustomValidator(check_even)
    assert v.validate(4).ok is True
    assert v.validate(3).ok is False
    print("[PASS] Custom Validator")


def test_function_transformer():
    """测试函数转换器"""
    t = FunctionTransformer(lambda x: x * 2, name="double")
    assert t.transform(5) == 10
    print("[PASS] Function Transformer")


def test_filter_transformer():
    """测试过滤转换器"""
    t = FilterTransformer(lambda x: x > 0)
    assert t.transform([1, -2, 3, 0, 5]) == [1, 3, 5]
    assert t.transform(-1) is None
    print("[PASS] Filter Transformer")


def test_map_transformer():
    """测试映射转换器"""
    t = MapTransformer(lambda x: x.upper())
    assert t.transform(["a", "b", "c"]) == ["A", "B", "C"]
    assert t.transform("hello") == "HELLO"
    print("[PASS] Map Transformer")


def test_chained_transformer():
    """测试链式转换器"""
    t1 = FunctionTransformer(lambda x: x + 1)
    t2 = FunctionTransformer(lambda x: x * 2)
    chained = t1 | t2
    assert chained.transform(3) == 8  # (3+1)*2
    print("[PASS] Chained Transformer")


def test_pipeline_basic():
    """测试基础流水线"""
    pipeline = DataPipeline("test_pipeline")

    pipeline.add_stage(
        extract_stage("extract", lambda data, ctx: data * 2)
    ).add_stage(
        transform_stage("transform", FunctionTransformer(lambda x: x + 10))
    ).add_stage(
        load_stage("load", lambda data, ctx: {"result": data})
    )

    result = pipeline.run(5)
    assert result.status == PipelineStatus.SUCCESS
    assert result.output == {"result": 20}  # (5*2)+10=20
    print("[PASS] Pipeline Basic")


def test_pipeline_with_validation():
    """测试带验证的流水线"""
    pipeline = DataPipeline("validated_pipeline")

    stage = FunctionStage(
        "process",
        lambda data, ctx: data * 2,
        input_validators=[TypeValidator(int), RangeValidator(min_value=0)],
        output_validators=[RangeValidator(max_value=100)],
    )
    pipeline.add_stage(stage)

    result = pipeline.run(30)
    assert result.status == PipelineStatus.SUCCESS
    assert result.output == 60

    result2 = pipeline.run(-5)
    assert result2.status == PipelineStatus.FAILED
    print("[PASS] Pipeline with Validation")


def test_pipeline_stage_dependencies():
    """测试阶段依赖"""
    pipeline = DataPipeline("dependency_pipeline")

    stage1 = FunctionStage("stage1", lambda data, ctx: data + 1)
    stage2 = FunctionStage("stage2", lambda data, ctx: data * 2)
    stage2.add_dependency("stage1")

    pipeline.add_stage(stage1).add_stage(stage2)
    result = pipeline.run(5)
    assert result.status == PipelineStatus.SUCCESS
    assert result.output == 12  # (5+1)*2
    print("[PASS] Pipeline Stage Dependencies")


def test_pipeline_context():
    """测试流水线上下文"""
    pipeline = DataPipeline("context_pipeline")
    pipeline.set_context("multiplier", 3)

    def multiply(data, ctx):
        return data * ctx.get("multiplier", 1)

    pipeline.add_stage(FunctionStage("multiply", multiply))
    result = pipeline.run(7)
    assert result.output == 21
    assert result.context["stage.multiply.output"] == 21
    print("[PASS] Pipeline Context")


def test_pipeline_error_handling():
    """测试流水线错误处理"""
    pipeline = DataPipeline("error_pipeline")

    def fail_stage(data, ctx):
        raise ValueError("故意失败")

    pipeline.add_stage(FunctionStage("fail", fail_stage))
    result = pipeline.run(1)
    assert result.status == PipelineStatus.FAILED
    assert result.stage_results[0].status == StageStatus.FAILED
    assert "故意失败" in result.stage_results[0].error
    print("[PASS] Pipeline Error Handling")


def test_pipeline_error_continue():
    """测试错误继续模式"""
    pipeline = DataPipeline("error_continue_pipeline")

    def fail_stage(data, ctx):
        raise ValueError("故意失败")

    pipeline.add_stage(FunctionStage("fail", fail_stage))
    result = pipeline.run_with_error_handling(1, on_error="continue")
    assert result.status == PipelineStatus.SUCCESS
    print("[PASS] Pipeline Error Continue")


def test_etl_pipeline():
    """测试ETL流水线"""
    pipeline = DataPipeline("etl_pipeline")

    # Extract: 从列表中读取数据
    pipeline.add_stage(extract_stage("extract", lambda data, ctx: data))

    # Transform: 过滤和映射
    transformer = FilterTransformer(lambda x: x > 0) | MapTransformer(lambda x: x * x)
    pipeline.add_stage(transform_stage("transform", transformer))

    # Load: 汇总
    pipeline.add_stage(load_stage("load", lambda data, ctx: {"squares": data, "sum": sum(data)}))

    result = pipeline.run([1, -2, 3, -4, 5])
    assert result.status == PipelineStatus.SUCCESS
    assert result.output["squares"] == [1, 9, 25]
    assert result.output["sum"] == 35
    print("[PASS] ETL Pipeline")


def test_pipeline_result_summary():
    """测试流水线结果汇总"""
    pipeline = DataPipeline("summary_pipeline")
    pipeline.add_stage(FunctionStage("s1", lambda d, c: d + 1))
    pipeline.add_stage(FunctionStage("s2", lambda d, c: d * 2))

    result = pipeline.run(5)
    assert result.status == PipelineStatus.SUCCESS
    assert result.output == 12
    assert result.duration_ms >= 0
    assert len(result.stage_results) == 2
    assert result.to_dict()["status"] == "success"
    print("[PASS] Pipeline Result Summary")


def test_stage_skip_dependency():
    """测试依赖缺失导致跳过"""
    pipeline = DataPipeline("skip_pipeline")

    stage_a = FunctionStage("a", lambda d, c: d)
    stage_b = FunctionStage("b", lambda d, c: d)
    stage_b.add_dependency("nonexistent")

    pipeline.add_stage(stage_a).add_stage(stage_b)
    result = pipeline.run(1)
    assert result.stage_results[0].status == StageStatus.SUCCESS
    assert result.stage_results[1].status == StageStatus.SKIPPED
    print("[PASS] Stage Skip Dependency")


def run_all_tests():
    print("=" * 50)
    print("阶段62验证：数据流水线")
    print("=" * 50)

    tests = [
        test_validation_result,
        test_type_validator,
        test_range_validator,
        test_not_null_validator,
        test_custom_validator,
        test_function_transformer,
        test_filter_transformer,
        test_map_transformer,
        test_chained_transformer,
        test_pipeline_basic,
        test_pipeline_with_validation,
        test_pipeline_stage_dependencies,
        test_pipeline_context,
        test_pipeline_error_handling,
        test_pipeline_error_continue,
        test_etl_pipeline,
        test_pipeline_result_summary,
        test_stage_skip_dependency,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 50)
    print(f"结果：通过 {passed} / 失败 {failed} / 总计 {len(tests)}")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
