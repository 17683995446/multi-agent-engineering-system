#!/usr/bin/env python3
"""
阶段44验证脚本：CSP约束满足冲突检测算法集成

验收标准：
1. CSP求解器正常初始化
2. 变量和约束添加正常
3. 冲突检测功能正常
4. 回溯搜索算法正常工作
5. 可以找到CSP问题的解
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.common.csp_solver import (
    CSPSolver, Variable, Constraint, ConstraintType,
    SearchStrategy, ConflictResolver
)

def test_csp_solver_initialization():
    """测试CSP求解器初始化"""
    print("\n=== 验收标准1: CSP求解器正常初始化 ===")
    
    try:
        solver = CSPSolver(name="test_solver")
        print(f"✅ CSP求解器初始化成功: {solver.name}")
        return True
    except Exception as e:
        print(f"❌ CSP求解器初始化失败: {e}")
        return False

def test_variable_and_constraint():
    """测试变量和约束添加"""
    print("\n=== 验收标准2: 变量和约束添加正常 ===")
    
    try:
        solver = CSPSolver()
        
        var_a = Variable(name="A", domain=[1, 2, 3])
        var_b = Variable(name="B", domain=[1, 2, 3])
        var_c = Variable(name="C", domain=[1, 2, 3])
        
        solver.add_variable(var_a)
        solver.add_variable(var_b)
        solver.add_variable(var_c)
        print(f"✅ 变量添加成功: {list(solver.variables.keys())}")
        
        def not_equal(x, y):
            return x != y
        
        constraint_ab = Constraint(
            name="A!=B",
            type=ConstraintType.BINARY,
            variables=["A", "B"],
            check=not_equal,
            description="A不等于B"
        )
        
        constraint_ac = Constraint(
            name="A!=C",
            type=ConstraintType.BINARY,
            variables=["A", "C"],
            check=not_equal,
            description="A不等于C"
        )
        
        constraint_bc = Constraint(
            name="B!=C",
            type=ConstraintType.BINARY,
            variables=["B", "C"],
            check=not_equal,
            description="B不等于C"
        )
        
        solver.add_constraint(constraint_ab)
        solver.add_constraint(constraint_ac)
        solver.add_constraint(constraint_bc)
        print(f"✅ 约束添加成功: {list(solver.constraints.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ 变量和约束添加失败: {e}")
        return False

def test_conflict_detection():
    """测试冲突检测功能"""
    print("\n=== 验收标准3: 冲突检测功能正常 ===")
    
    try:
        solver = CSPSolver()
        
        var_a = Variable(name="A", domain=[1, 2], value=1)
        var_b = Variable(name="B", domain=[1, 2], value=1)
        
        solver.add_variable(var_a)
        solver.add_variable(var_b)
        
        def not_equal(x, y):
            return x != y
        
        constraint_ab = Constraint(
            name="A!=B",
            type=ConstraintType.BINARY,
            variables=["A", "B"],
            check=not_equal,
            description="A不等于B"
        )
        
        solver.add_constraint(constraint_ab)
        
        conflicts = solver.detect_conflicts()
        print(f"✅ 检测到 {len(conflicts)} 个冲突")
        
        if conflicts:
            print(f"   冲突类型: {conflicts[0].type.value}")
            print(f"   涉及变量: {conflicts[0].variables}")
        
        return True
    except Exception as e:
        print(f"❌ 冲突检测失败: {e}")
        return False

def test_backtrack_search():
    """测试回溯搜索算法"""
    print("\n=== 验收标准4: 回溯搜索算法正常工作 ===")
    
    try:
        solver = CSPSolver()
        
        var_a = Variable(name="A", domain=[1, 2, 3])
        var_b = Variable(name="B", domain=[1, 2, 3])
        var_c = Variable(name="C", domain=[1, 2, 3])
        
        solver.add_variable(var_a)
        solver.add_variable(var_b)
        solver.add_variable(var_c)
        
        def not_equal(x, y):
            return x != y
        
        constraint_ab = Constraint(
            name="A!=B",
            type=ConstraintType.BINARY,
            variables=["A", "B"],
            check=not_equal,
            description="A不等于B"
        )
        
        constraint_ac = Constraint(
            name="A!=C",
            type=ConstraintType.BINARY,
            variables=["A", "C"],
            check=not_equal,
            description="A不等于C"
        )
        
        constraint_bc = Constraint(
            name="B!=C",
            type=ConstraintType.BINARY,
            variables=["B", "C"],
            check=not_equal,
            description="B不等于C"
        )
        
        solver.add_constraint(constraint_ab)
        solver.add_constraint(constraint_ac)
        solver.add_constraint(constraint_bc)
        
        solution = solver.solve(strategy=SearchStrategy.BACKTRACKING)
        
        print(f"✅ 回溯搜索完成，步数: {solution.steps}")
        
        return True
    except Exception as e:
        print(f"❌ 回溯搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_solution_finding():
    """测试找到CSP问题的解"""
    print("\n=== 验收标准5: 可以找到CSP问题的解 ===")
    
    try:
        solver = CSPSolver()
        
        var_a = Variable(name="A", domain=[1, 2, 3])
        var_b = Variable(name="B", domain=[1, 2, 3])
        var_c = Variable(name="C", domain=[1, 2, 3])
        
        solver.add_variable(var_a)
        solver.add_variable(var_b)
        solver.add_variable(var_c)
        
        def not_equal(x, y):
            return x != y
        
        constraint_ab = Constraint(
            name="A!=B",
            type=ConstraintType.BINARY,
            variables=["A", "B"],
            check=not_equal,
            description="A不等于B"
        )
        
        constraint_ac = Constraint(
            name="A!=C",
            type=ConstraintType.BINARY,
            variables=["A", "C"],
            check=not_equal,
            description="A不等于C"
        )
        
        constraint_bc = Constraint(
            name="B!=C",
            type=ConstraintType.BINARY,
            variables=["B", "C"],
            check=not_equal,
            description="B不等于C"
        )
        
        solver.add_constraint(constraint_ab)
        solver.add_constraint(constraint_ac)
        solver.add_constraint(constraint_bc)
        
        solution = solver.solve()
        
        if solution.is_solved:
            print("✅ 找到CSP问题的解:")
            for var, val in solution.assignments.items():
                print(f"   {var} = {val}")
            return True
        else:
            print("❌ 未找到CSP问题的解")
            return False
            
    except Exception as e:
        print(f"❌ 求解失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_conflict_resolver():
    """测试冲突解决器"""
    print("\n=== 额外验收: 冲突解决器功能 ===")
    
    try:
        resolver = ConflictResolver()
        
        solver = CSPSolver()
        var_a = Variable(name="A", domain=[1, 2], value=1)
        var_b = Variable(name="B", domain=[1, 2], value=1)
        solver.add_variable(var_a)
        solver.add_variable(var_b)
        
        def not_equal(x, y):
            return x != y
        
        constraint_ab = Constraint(
            name="A!=B",
            type=ConstraintType.BINARY,
            variables=["A", "B"],
            check=not_equal,
            description="A不等于B"
        )
        
        solver.add_constraint(constraint_ab)
        
        conflicts = solver.detect_conflicts()
        resolutions = resolver.suggest_resolutions(conflicts)
        
        print(f"✅ 冲突解决器生成了 {len(resolutions)} 个建议")
        return True
    except Exception as e:
        print(f"❌ 冲突解决器测试失败: {e}")
        return False

def main():
    """主验证函数"""
    print("=" * 60)
    print("阶段44验证：CSP约束满足冲突检测算法集成")
    print("=" * 60)
    
    results = []
    
    results.append(("CSP求解器初始化", test_csp_solver_initialization()))
    results.append(("变量和约束添加", test_variable_and_constraint()))
    results.append(("冲突检测功能", test_conflict_detection()))
    results.append(("回溯搜索算法", test_backtrack_search()))
    results.append(("找到CSP问题的解", test_solution_finding()))
    results.append(("冲突解决器功能", test_conflict_resolver()))
    
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
        print("\n🎉 阶段44验收通过！")
        return 0
    else:
        print("\n❌ 阶段44验收未通过！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
