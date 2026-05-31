"""
文档Agent - 遵循第一性原理
核心功能：
1. 实例启动正常
2. 自动生成需求&设计文档
3. 文档归档与版本化
4. 代码变更触发文档更新
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import hashlib
from src.agents.base import BaseAgent
from src.common.utils import setup_logger

logger = setup_logger(__name__)


class DocumentType(Enum):
    """文档类型"""
    REQUIREMENT = "requirement"
    DESIGN = "design"
    API = "api"
    ARCHITECTURE = "architecture"
    USER_GUIDE = "user_guide"
    CHANGELOG = "changelog"


class DocumentStatus(Enum):
    """文档状态"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


@dataclass
class DocumentVersion:
    """文档版本"""
    version_id: str
    version_number: int
    content: str
    author: str
    created_at: str
    change_summary: str
    hash: str


@dataclass
class Document:
    """文档对象"""
    doc_id: str
    doc_type: DocumentType
    title: str
    current_version: int
    versions: List[DocumentVersion] = field(default_factory=list)
    status: DocumentStatus = DocumentStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)


@dataclass
class CodeChange:
    """代码变更记录"""
    change_id: str
    file_path: str
    change_type: str  # "add", "modify", "delete"
    timestamp: str
    before: Optional[str] = None
    after: Optional[str] = None


class DocumentAgent(BaseAgent):
    """文档Agent"""

    def __init__(self):
        super().__init__("DocumentAgent")
        self.is_running = False
        self.documents: Dict[str, Document] = {}
        self.change_history: List[CodeChange] = []
        self.doc_root: Path = Path("/workspace/docs")

    def start(self):
        """启动Agent"""
        self.is_running = True
        self.doc_root.mkdir(exist_ok=True)
        logger.info(f"文档Agent {self.name} 已启动，文档目录: {self.doc_root}")

    def stop(self):
        """停止Agent"""
        self.is_running = False
        logger.info(f"文档Agent {self.name} 已停止")

    def _calculate_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def create_document(
        self,
        doc_type: DocumentType,
        title: str,
        content: str,
        author: str = "DocumentAgent",
        tags: Optional[List[str]] = None
    ) -> Document:
        """创建新文档"""
        if not self.is_running:
            self.start()

        doc_id = f"doc_{len(self.documents) + 1}"
        initial_version = DocumentVersion(
            version_id=f"v1",
            version_number=1,
            content=content,
            author=author,
            created_at=datetime.now().isoformat(),
            change_summary="初始版本",
            hash=self._calculate_hash(content)
        )

        doc = Document(
            doc_id=doc_id,
            doc_type=doc_type,
            title=title,
            current_version=1,
            versions=[initial_version],
            tags=tags or []
        )

        self.documents[doc_id] = doc
        self._save_document(doc)
        logger.info(f"文档创建成功: {doc.title} (ID: {doc_id})")
        return doc

    def update_document(
        self,
        doc_id: str,
        new_content: str,
        change_summary: str,
        author: str = "DocumentAgent"
    ) -> Optional[DocumentVersion]:
        """更新文档版本"""
        if doc_id not in self.documents:
            logger.warning(f"文档不存在: {doc_id}")
            return None

        doc = self.documents[doc_id]
        current_version = doc.current_version
        new_version_number = current_version + 1

        new_version = DocumentVersion(
            version_id=f"v{new_version_number}",
            version_number=new_version_number,
            content=new_content,
            author=author,
            created_at=datetime.now().isoformat(),
            change_summary=change_summary,
            hash=self._calculate_hash(new_content)
        )

        doc.versions.append(new_version)
        doc.current_version = new_version_number
        doc.last_updated = datetime.now().isoformat()
        doc.status = DocumentStatus.REVIEW if new_version_number > 1 else doc.status
        self._save_document(doc)

        logger.info(f"文档更新成功: {doc.title} -> 版本 {new_version_number}")
        return new_version

    def _save_document(self, doc: Document):
        """保存文档到文件系统"""
        type_dir = self.doc_root / doc.doc_type.value
        type_dir.mkdir(exist_ok=True)

        doc_file = type_dir / f"{doc.doc_id}.json"
        with open(doc_file, "w", encoding="utf-8") as f:
            doc_data = {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "type": doc.doc_type.value,
                "status": doc.status.value,
                "current_version": doc.current_version,
                "created_at": doc.created_at,
                "last_updated": doc.last_updated,
                "tags": doc.tags,
                "versions": [
                    {
                        "version_id": v.version_id,
                        "number": v.version_number,
                        "content": v.content,
                        "author": v.author,
                        "created_at": v.created_at,
                        "change_summary": v.change_summary,
                        "hash": v.hash
                    } for v in doc.versions
                ]
            }
            json.dump(doc_data, f, indent=2, ensure_ascii=False)

    def generate_requirement_document(
        self,
        feature_name: str,
        description: str,
        acceptance_criteria: List[str],
        dependencies: Optional[List[str]] = None
    ) -> Document:
        """生成需求文档"""
        content_lines = [
            f"# {feature_name}",
            "",
            "## 需求描述",
            "",
            description,
            "",
            "## 验收标准",
            ""
        ]

        for i, criterion in enumerate(acceptance_criteria, 1):
            content_lines.append(f"{i}. {criterion}")

        if dependencies:
            content_lines.append("")
            content_lines.append("## 依赖项")
            content_lines.append("")
            for dep in dependencies:
                content_lines.append(f"- {dep}")

        content_lines.append("")
        content_lines.append(f"---")
        content_lines.append(f"*生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        content = "\n".join(content_lines)

        return self.create_document(
            doc_type=DocumentType.REQUIREMENT,
            title=f"{feature_name} - 需求文档",
            content=content,
            tags=["requirement", feature_name.lower().replace(" ", "_")]
        )

    def generate_design_document(
        self,
        component_name: str,
        architecture_overview: str,
        module_list: List[Dict[str, str]]
    ) -> Document:
        """生成设计文档"""
        content_lines = [
            f"# {component_name} - 设计文档",
            "",
            "## 架构概述",
            "",
            architecture_overview,
            "",
            "## 模块设计",
            ""
        ]

        for module in module_list:
            content_lines.append(f"### {module.get('name', 'Unknown')}")
            content_lines.append("")
            content_lines.append(f"职责: {module.get('responsibility', '待定义')}")
            content_lines.append(f"")
            if "interfaces" in module:
                content_lines.append(f"接口: {module['interfaces']}")
                content_lines.append("")

        content_lines.append("")
        content_lines.append(f"---")
        content_lines.append(f"*生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        content = "\n".join(content_lines)

        return self.create_document(
            doc_type=DocumentType.DESIGN,
            title=f"{component_name} - 设计文档",
            content=content,
            tags=["design", component_name.lower().replace(" ", "_")]
        )

    def generate_changelog(self) -> Document:
        """生成变更日志文档"""
        content_lines = [
            "# 变更日志",
            "",
            "## 版本历史",
            ""
        ]

        sorted_changes = sorted(self.change_history, key=lambda x: x.timestamp, reverse=True)

        for change in sorted_changes:
            content_lines.append(f"- [{change.timestamp[:19]}] {change.change_type.upper()}: {change.file_path}")

        if not sorted_changes:
            content_lines.append("暂未记录变更")

        content_lines.append("")
        content_lines.append(f"---")
        content_lines.append(f"*生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        content = "\n".join(content_lines)

        existing = next(
            (d for d in self.documents.values() if d.title == "变更日志"), None
        )

        if existing:
            self.update_document(
                existing.doc_id,
                content,
                "更新变更日志"
            )
            return existing

        return self.create_document(
            doc_type=DocumentType.CHANGELOG,
            title="变更日志",
            content=content,
            tags=["changelog"]
        )

    def record_code_change(
        self,
        file_path: str,
        change_type: str,
        before: Optional[str] = None,
        after: Optional[str] = None
    ) -> CodeChange:
        """记录代码变更"""
        change = CodeChange(
            change_id=f"chg_{len(self.change_history) + 1}",
            file_path=file_path,
            change_type=change_type,
            timestamp=datetime.now().isoformat(),
            before=before,
            after=after
        )
        self.change_history.append(change)
        logger.info(f"记录代码变更: {change_type} - {file_path}")
        return change

    def archive_document(self, doc_id: str) -> bool:
        """归档文档"""
        if doc_id not in self.documents:
            logger.warning(f"文档不存在: {doc_id}")
            return False

        doc = self.documents[doc_id]
        if doc.status == DocumentStatus.ARCHIVED:
            return True

        doc.status = DocumentStatus.ARCHIVED
        logger.info(f"文档已归档: {doc.title} (ID: {doc_id})")
        return True

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self.documents.get(doc_id)

    def list_documents(self, doc_type: Optional[DocumentType] = None) -> List[Document]:
        """列出文档"""
        docs = list(self.documents.values())
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        return docs

    def execute(self, task: Any) -> Any:
        """Agent执行入口"""
        if isinstance(task, dict) and "action" in task:
            action = task["action"]
            if action == "create_requirement":
                doc = self.generate_requirement_document(
                    task["feature_name"],
                    task["description"],
                    task["acceptance_criteria"],
                    task.get("dependencies")
                )
                return {"doc_id": doc.doc_id, "title": doc.title}
            elif action == "create_design":
                doc = self.generate_design_document(
                    task["component_name"],
                    task["architecture_overview"],
                    task.get("module_list", [])
                )
                return {"doc_id": doc.doc_id, "title": doc.title}
            elif action == "record_change":
                self.record_code_change(
                    task["file_path"],
                    task["change_type"],
                    task.get("before"),
                    task.get("after")
                )
                return {"status": "success"}
            elif action == "generate_changelog":
                doc = self.generate_changelog()
                return {"doc_id": doc.doc_id}
        return {"error": "Invalid task format"}


def demo_document_agent():
    """演示文档Agent"""
    print("=" * 70)
    print("文档Agent演示")
    print("=" * 70)
    print()

    agent = DocumentAgent()
    agent.start()

    print("步骤1: 生成需求文档")
    req_doc = agent.generate_requirement_document(
        "用户管理模块",
        "实现用户注册、登录、权限管理功能",
        [
            "支持用户注册",
            "支持邮箱密码登录",
            "支持角色权限管理",
            "支持用户信息修改"
        ],
        ["用户数据库", "邮件服务"]
    )
    print(f"✅ 需求文档创建: {req_doc.title}")
    print(f"   版本: {req_doc.current_version}")
    print()

    print("步骤2: 生成设计文档")
    design_doc = agent.generate_design_document(
        "用户管理",
        "采用三层架构设计，包括Controller、Service、DAO层",
        [
            {
                "name": "UserController",
                "responsibility": "处理HTTP请求与响应",
                "interfaces": "POST /api/user, GET /api/user/:id"
            },
            {
                "name": "UserService",
                "responsibility": "业务逻辑处理",
                "interfaces": "register(), login(), get_profile()"
            },
            {
                "name": "UserDAO",
                "responsibility": "数据库操作",
                "interfaces": "CRUD接口"
            }
        ]
    )
    print(f"✅ 设计文档创建: {design_doc.title}")
    print()

    print("步骤3: 记录代码变更")
    change1 = agent.record_code_change(
        "/src/modules/user/controller.py",
        "add",
        None,
        "新增用户注册接口实现"
    )
    change2 = agent.record_code_change(
        "/src/modules/user/service.py",
        "modify",
        "旧的业务逻辑",
        "优化后的业务逻辑"
    )
    print(f"✅ 记录了 {len(agent.change_history)} 个代码变更")
    print()

    print("步骤4: 生成变更日志")
    changelog = agent.generate_changelog()
    print(f"✅ 变更日志生成: {changelog.title}")
    print()

    print("步骤5: 列出所有文档")
    all_docs = agent.list_documents()
    for doc in all_docs:
        print(f"  - {doc.title} ({doc.doc_type.value})")
    print()

    print("=" * 70)
    print("✅ 演示完成")


if __name__ == "__main__":
    demo_document_agent()
