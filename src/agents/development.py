"""
开发Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 支持代码新增、修改、重构、修复操作
3. 严格遵循原子化规范编码
4. 无越权修改架构、无违规改动依赖
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
from src.agents.base import BaseAgent
from src.common.utils import setup_logger
from src.code.variable_atom_scanner import VariableAtomScanner
from src.code.method_atom_scanner import MethodAtomScanner
from src.code.class_atom_scanner import ClassAtomScanner
from src.code.naming_validator import NamingValidator

logger = setup_logger(__name__)


class CodeOperationType(Enum):
    """代码操作类型"""
    NEW_FILE = "new_file"
    MODIFY = "modify"
    REFACTOR = "refactor"
    FIX = "fix"
    DELETE = "delete"


class ChangeStatus(Enum):
    """变更状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class CodeChange:
    """代码变更"""
    change_id: str
    file_path: str
    operation: CodeOperationType
    description: str
    original_code: Optional[str] = None
    new_code: Optional[str] = None
    line_number: int = 0
    status: ChangeStatus = ChangeStatus.PENDING
    created_at: str = ""
    applied_at: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class AtomicValidation:
    """原子化验证结果"""
    valid: bool
    issues: List[str]
    suggestions: List[str]


class DevelopmentAgent(BaseAgent):
    """开发Agent"""

    def __init__(self):
        super().__init__("DevelopmentAgent")
        self.is_running = False
        self.pending_changes: List[CodeChange] = []
        self.applied_changes: List[CodeChange] = []
        self.var_scanner = VariableAtomScanner()
        self.method_scanner = MethodAtomScanner()
        self.class_scanner = ClassAtomScanner()
        self.naming_validator = NamingValidator()

    def start(self):
        """启动Agent"""
        self.is_running = True
        logger.info(f"开发Agent {self.name} 已启动")

    def stop(self):
        """停止Agent"""
        self.is_running = False
        logger.info(f"开发Agent {self.name} 已停止")

    def create_file(self, file_path: str, content: str, description: str) -> CodeChange:
        """创建新文件"""
        if not self.is_running:
            self.start()

        change_id = f"change_new_{len(self.pending_changes) + 1}"
        change = CodeChange(
            change_id=change_id,
            file_path=file_path,
            operation=CodeOperationType.NEW_FILE,
            description=description,
            new_code=content,
            created_at=datetime.now().isoformat()
        )

        # 验证原子化规范
        validation = self._validate_atomic_rules(content)
        if not validation.valid:
            change.validation_errors = validation.issues
            logger.warning(f"代码违反原子化规范：{validation.issues}")
        else:
            logger.info(f"文件创建准备就绪：{file_path}")

        self.pending_changes.append(change)
        return change

    def modify_file(self, file_path: str, line_num: int, old_content: str, new_content: str, description: str) -> CodeChange:
        """修改文件内容"""
        if not self.is_running:
            self.start()

        change_id = f"change_mod_{len(self.pending_changes) + 1}"
        change = CodeChange(
            change_id=change_id,
            file_path=file_path,
            operation=CodeOperationType.MODIFY,
            description=description,
            original_code=old_content,
            new_code=new_content,
            line_number=line_num,
            created_at=datetime.now().isoformat()
        )

        # 验证修改是否违规（不修改架构和依赖）
        if self._is_architecture_change(new_content) or self._is_dependency_change(new_content):
            change.validation_errors.append("违规修改：不允许修改架构或依赖")
            change.status = ChangeStatus.REJECTED
            logger.error(f"拒绝变更：{change_id} 尝试修改架构或依赖")
        else:
            # 验证原子化规范
            validation = self._validate_atomic_rules(new_content)
            if not validation.valid:
                change.validation_errors = validation.issues
            logger.info(f"文件修改准备就绪：{file_path}")

        self.pending_changes.append(change)
        return change

    def refactor_code(self, file_path: str, description: str, refactor_type: str) -> CodeChange:
        """重构代码"""
        if not self.is_running:
            self.start()

        change_id = f"change_ref_{len(self.pending_changes) + 1}"
        change = CodeChange(
            change_id=change_id,
            file_path=file_path,
            operation=CodeOperationType.REFACTOR,
            description=description,
            created_at=datetime.now().isoformat()
        )

        # 验证重构不修改架构或依赖
        # 这里简化处理，实际应该对比重构前后的差异
        if "dependency" in refactor_type.lower() or "architecture" in refactor_type.lower():
            change.validation_errors.append("违规重构：不允许修改架构或依赖")
            change.status = ChangeStatus.REJECTED
            logger.error(f"拒绝重构：{change_id} 尝试修改架构或依赖")
        else:
            logger.info(f"代码重构准备就绪：{file_path}")

        self.pending_changes.append(change)
        return change

    def fix_issue(self, file_path: str, line_num: int, issue_description: str, fix_code: str) -> CodeChange:
        """修复问题"""
        if not self.is_running:
            self.start()

        change_id = f"change_fix_{len(self.pending_changes) + 1}"
        change = CodeChange(
            change_id=change_id,
            file_path=file_path,
            operation=CodeOperationType.FIX,
            description=issue_description,
            new_code=fix_code,
            line_number=line_num,
            created_at=datetime.now().isoformat()
        )

        # 验证修复内容
        validation = self._validate_atomic_rules(fix_code)
        if not validation.valid:
            change.validation_errors = validation.issues
        logger.info(f"问题修复准备就绪：{file_path}")

        self.pending_changes.append(change)
        return change

    def apply_change(self, change_id: str) -> bool:
        """应用变更"""
        for change in self.pending_changes:
            if change.change_id == change_id:
                if change.status == ChangeStatus.REJECTED:
                    logger.error(f"无法应用被拒绝的变更：{change_id}")
                    return False
                if change.validation_errors:
                    logger.warning(f"应用有验证问题的变更：{change_id}")

                # 实际应用逻辑（演示用）
                change.status = ChangeStatus.APPLIED
                change.applied_at = datetime.now().isoformat()
                self.applied_changes.append(change)
                self.pending_changes.remove(change)
                logger.info(f"变更已应用：{change_id}")
                return True
        return False

    def list_changes(self, status: Optional[ChangeStatus] = None) -> List[Dict[str, Any]]:
        """列出现有变更"""
        changes = []
        target_list = self.pending_changes if not status else [
            c for c in self.pending_changes if c.status == status
        ]
        for change in target_list:
            changes.append({
                "id": change.change_id,
                "file": change.file_path,
                "operation": change.operation.value,
                "description": change.description,
                "status": change.status.value,
                "errors": change.validation_errors
            })
        return changes

    def _validate_atomic_rules(self, code: str) -> AtomicValidation:
        """验证原子化规则"""
        issues = []
        suggestions = []

        # 这里简化处理，实际应该调用完整的原子化扫描器
        if len(code) > 1000 and "class" in code and "def" in code:
            issues.append("代码可能过长，建议拆分为更小的模块")
        if "temp = " in code or "data = " in code:
            suggestions.append("建议使用更有语义的变量名")

        return AtomicValidation(
            valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions
        )

    def _is_architecture_change(self, content: str) -> bool:
        """检查是否是架构变更"""
        keywords = ["ARCHITECTURE", "class ", "Agent", "register_agent"]
        for kw in keywords:
            if kw in content:
                return True
        return False

    def _is_dependency_change(self, content: str) -> bool:
        """检查是否是依赖变更"""
        keywords = ["import ", "from ", "sys.path", "requirements", "setup.py"]
        for kw in keywords:
            if kw in content:
                return True
        return False

    def execute(self, task: Any) -> Any:
        """Agent执行入口"""
        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "create_file":
                change = self.create_file(
                    task["file_path"],
                    task.get("content", ""),
                    task.get("description", "")
                )
                return {"status": "ok", "change_id": change.change_id}
            elif action == "modify_file":
                change = self.modify_file(
                    task["file_path"],
                    task.get("line", 0),
                    task.get("old_content", ""),
                    task.get("new_content", ""),
                    task.get("description", "")
                )
                return {"status": "ok", "change_id": change.change_id}
            elif action == "refactor":
                change = self.refactor_code(
                    task["file_path"],
                    task.get("description", ""),
                    task.get("type", "")
                )
                return {"status": "ok", "change_id": change.change_id}
            elif action == "fix":
                change = self.fix_issue(
                    task["file_path"],
                    task.get("line", 0),
                    task.get("issue", ""),
                    task.get("fix_code", "")
                )
                return {"status": "ok", "change_id": change.change_id}
            elif action == "apply":
                success = self.apply_change(task["change_id"])
                return {"status": "ok" if success else "error"}
            elif action == "list":
                return {"changes": self.list_changes()}
        return {"error": "Invalid task format"}


def demo_development_agent():
    """演示开发Agent"""
    print("=" * 70)
    print("开发Agent演示")
    print("=" * 70)
    print()

    agent = DevelopmentAgent()
    agent.start()

    # 1. 创建文件
    print("步骤1：创建新文件")
    change1 = agent.create_file(
        "/tmp/demo_utils.py",
        '''"""演示工具模块"""

def calculate_sum(a: int, b: int) -> int:
    """计算两个数的和"""
    return a + b

def calculate_product(a: int, b: int) -> int:
    """计算两个数的乘积"""
    return a * b
''',
        "创建演示工具模块"
    )
    print(f"  变更ID：{change1.change_id}")
    print(f"  状态：{change1.status.value}")
    print()

    # 2. 修改文件（正常）
    print("步骤2：修改文件")
    change2 = agent.modify_file(
        "/tmp/demo_utils.py",
        5,
        "def calculate_sum(a: int, b: int) -> int:",
        "def calculate_sum(a: int, b: int, c: int = 0) -> int:",
        "增加可选参数c"
    )
    print(f"  变更ID：{change2.change_id}")
    print(f"  状态：{change2.status.value}")
    print()

    # 3. 尝试违规修改（被拒绝）
    print("步骤3：尝试违规修改（依赖文件）")
    change3 = agent.modify_file(
        "/tmp/demo_utils.py",
        1,
        '"""演示工具模块"""',
        "import sys\n'''演示工具模块'''",
        "尝试添加导入"
    )
    print(f"  变更ID：{change3.change_id}")
    print(f"  状态：{change3.status.value}")
    print(f"  错误：{change3.validation_errors}")
    print()

    # 4. 应用前两个变更
    print("步骤4：应用前两个变更")
    agent.apply_change(change1.change_id)
    agent.apply_change(change2.change_id)
    print(f"  已应用变更数：{len(agent.applied_changes)}")
    print()

    # 5. 列出变更
    print("步骤5：列出所有变更")
    all_changes = agent.list_changes()
    for ch in all_changes:
        print(f"  [{ch['status']}] {ch['id']}: {ch['description']}")
    print()

    print("=" * 70)
    print("✅ 演示完成")


if __name__ == "__main__":
    demo_development_agent()
