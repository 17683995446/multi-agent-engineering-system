"""
知识库模块 - 公共层
职责：提供知识条目管理、全文搜索、标签分类、版本管理
依赖规则：依赖 utils.py（日志、异常）
"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

from .utils import setup_logger, SystemException, ValidationException


class KnowledgeBaseException(SystemException):
    """知识库异常"""
    def __init__(self, message: str, trace_id: Optional[str] = None):
        super().__init__(message, code="KNOWLEDGE_BASE_ERROR", trace_id=trace_id)


@dataclass
class KnowledgeEntry:
    """
    知识条目 - 知识库的基本单元

    字段：
    - id: 唯一标识
    - title: 标题
    - content: 内容
    - tags: 标签集合
    - category: 分类
    - version: 版本号
    - created_at: 创建时间
    - updated_at: 更新时间
    - author: 作者
    - metadata: 扩展元数据
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    tags: Set[str] = field(default_factory=set)
    category: str = "default"
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        """从字典创建"""
        data = dict(data)
        if "tags" in data and isinstance(data["tags"], list):
            data["tags"] = set(data["tags"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def bump_version(self) -> "KnowledgeEntry":
        """版本升级"""
        self.version += 1
        self.updated_at = datetime.now().isoformat()
        return self

    def add_tag(self, tag: str) -> "KnowledgeEntry":
        """添加标签"""
        self.tags.add(tag)
        self.updated_at = datetime.now().isoformat()
        return self

    def remove_tag(self, tag: str) -> "KnowledgeEntry":
        """移除标签"""
        self.tags.discard(tag)
        self.updated_at = datetime.now().isoformat()
        return self


class KnowledgeIndexer:
    """
    知识索引器 - 维护内容索引以加速搜索

    支持：
    - 倒排索引（关键词 -> 条目ID）
    - 标签索引（标签 -> 条目ID）
    - 分类索引（分类 -> 条目ID）
    """

    def __init__(self):
        self._inverted_index: Dict[str, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._category_index: Dict[str, Set[str]] = {}
        self.logger = setup_logger(__name__ + ".KnowledgeIndexer")

    def index_entry(self, entry: KnowledgeEntry) -> None:
        """为条目建立索引"""
        entry_id = entry.id

        # 倒排索引：分词标题和内容
        text = f"{entry.title} {entry.content}".lower()
        words = self._tokenize(text)
        for word in words:
            if word not in self._inverted_index:
                self._inverted_index[word] = set()
            self._inverted_index[word].add(entry_id)

        # 标签索引
        for tag in entry.tags:
            tag_key = tag.lower()
            if tag_key not in self._tag_index:
                self._tag_index[tag_key] = set()
            self._tag_index[tag_key].add(entry_id)

        # 分类索引
        cat_key = entry.category.lower()
        if cat_key not in self._category_index:
            self._category_index[cat_key] = set()
        self._category_index[cat_key].add(entry_id)

        self.logger.debug(f"Indexed entry {entry_id}: {len(words)} words, {len(entry.tags)} tags")

    def remove_entry(self, entry: KnowledgeEntry) -> None:
        """移除条目索引"""
        entry_id = entry.id

        # 移除倒排索引
        for word, ids in list(self._inverted_index.items()):
            ids.discard(entry_id)
            if not ids:
                del self._inverted_index[word]

        # 移除标签索引
        for tag, ids in list(self._tag_index.items()):
            ids.discard(entry_id)
            if not ids:
                del self._tag_index[tag]

        # 移除分类索引
        for cat, ids in list(self._category_index.items()):
            ids.discard(entry_id)
            if not ids:
                del self._category_index[cat]

        self.logger.debug(f"Removed index for entry {entry_id}")

    def search_by_keyword(self, keyword: str) -> Set[str]:
        """按关键词搜索，返回条目ID集合"""
        keyword = keyword.lower()
        result: Set[str] = set()
        for word, ids in self._inverted_index.items():
            if keyword in word or word in keyword:
                result.update(ids)
        return result

    def search_by_tag(self, tag: str) -> Set[str]:
        """按标签搜索"""
        return self._tag_index.get(tag.lower(), set()).copy()

    def search_by_category(self, category: str) -> Set[str]:
        """按分类搜索"""
        return self._category_index.get(category.lower(), set()).copy()

    def get_all_tags(self) -> Set[str]:
        """获取所有标签"""
        return set(self._tag_index.keys())

    def get_all_categories(self) -> Set[str]:
        """获取所有分类"""
        return set(self._category_index.keys())

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """简单分词：提取字母数字序列"""
        return re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text)


class KnowledgeSearch:
    """
    知识搜索 - 提供多种搜索策略

    支持：
    - 全文搜索
    - 标签搜索
    - 分类搜索
    - 组合搜索
    """

    def __init__(self, indexer: KnowledgeIndexer, entries: Dict[str, KnowledgeEntry]):
        self.indexer = indexer
        self.entries = entries
        self.logger = setup_logger(__name__ + ".KnowledgeSearch")

    def full_text_search(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """全文搜索"""
        if not query.strip():
            return []
        keywords = self.indexer._tokenize(query.lower())
        if not keywords:
            return []

        scores: Dict[str, int] = {}
        for kw in keywords:
            ids = self.indexer.search_by_keyword(kw)
            for entry_id in ids:
                scores[entry_id] = scores.get(entry_id, 0) + 1

        # 按得分排序
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for entry_id, score in sorted_ids[:limit]:
            if entry_id in self.entries:
                results.append(self.entries[entry_id])
        self.logger.debug(f"Full-text search '{query}' returned {len(results)} results")
        return results

    def tag_search(self, tags: List[str], match_all: bool = False) -> List[KnowledgeEntry]:
        """标签搜索"""
        if not tags:
            return []

        result_sets = [self.indexer.search_by_tag(tag) for tag in tags]
        if not result_sets:
            return []

        if match_all:
            ids = set.intersection(*result_sets) if result_sets else set()
        else:
            ids = set.union(*result_sets) if result_sets else set()

        return [self.entries[eid] for eid in ids if eid in self.entries]

    def category_search(self, category: str) -> List[KnowledgeEntry]:
        """分类搜索"""
        ids = self.indexer.search_by_category(category)
        return [self.entries[eid] for eid in ids if eid in self.entries]

    def combined_search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[KnowledgeEntry]:
        """组合搜索"""
        candidates: Optional[Set[str]] = None

        if category:
            cat_ids = self.indexer.search_by_category(category)
            candidates = cat_ids if candidates is None else candidates & cat_ids

        if tags:
            tag_ids = set()
            for tag in tags:
                tag_ids |= self.indexer.search_by_tag(tag)
            candidates = tag_ids if candidates is None else candidates & tag_ids

        if query:
            text_ids = set()
            keywords = self.indexer._tokenize(query.lower())
            for kw in keywords:
                text_ids |= self.indexer.search_by_keyword(kw)
            candidates = text_ids if candidates is None else candidates & text_ids

        if candidates is None:
            return list(self.entries.values())[:limit]

        results = [self.entries[eid] for eid in candidates if eid in self.entries]
        return results[:limit]


class KnowledgeBase:
    """
    知识库管理器 - 统一管理知识条目

    支持：
    - 知识条目CRUD
    - 全文搜索
    - 标签分类
    - 版本管理
    - 持久化存储
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._history: Dict[str, List[KnowledgeEntry]] = {}
        self._indexer = KnowledgeIndexer()
        self._search = KnowledgeSearch(self._indexer, self._entries)
        self.logger = setup_logger(__name__ + ".KnowledgeBase")

        if storage_path is None:
            from .utils import GlobalConfig
            storage_path = GlobalConfig.ROOT_DIR / "data" / "knowledge_base.json"
        self._storage_path = storage_path
        self._load()

    # ---- CRUD ----

    def create(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """创建知识条目"""
        if entry.id in self._entries:
            raise KnowledgeBaseException(f"Entry with id {entry.id} already exists")
        self._entries[entry.id] = entry
        self._indexer.index_entry(entry)
        self._save()
        self.logger.info(f"Created entry {entry.id}: {entry.title}")
        return entry

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """读取知识条目"""
        return self._entries.get(entry_id)

    def update(self, entry_id: str, **kwargs) -> KnowledgeEntry:
        """更新知识条目（自动版本升级）"""
        entry = self._entries.get(entry_id)
        if not entry:
            raise KnowledgeBaseException(f"Entry {entry_id} not found")

        # 保存历史
        if entry_id not in self._history:
            self._history[entry_id] = []
        self._history[entry_id].append(
            KnowledgeEntry.from_dict(entry.to_dict())
        )

        # 移除旧索引
        self._indexer.remove_entry(entry)

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(entry, key):
                if key == "tags" and isinstance(value, list):
                    value = set(value)
                setattr(entry, key, value)

        entry.bump_version()
        self._indexer.index_entry(entry)
        self._save()
        self.logger.info(f"Updated entry {entry_id} to version {entry.version}")
        return entry

    def delete(self, entry_id: str) -> bool:
        """删除知识条目"""
        entry = self._entries.pop(entry_id, None)
        if not entry:
            return False
        self._indexer.remove_entry(entry)
        self._history.pop(entry_id, None)
        self._save()
        self.logger.info(f"Deleted entry {entry_id}")
        return True

    def list_all(self) -> List[KnowledgeEntry]:
        """列出所有条目"""
        return list(self._entries.values())

    def count(self) -> int:
        """条目总数"""
        return len(self._entries)

    # ---- 搜索 ----

    def search(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """全文搜索"""
        return self._search.full_text_search(query, limit)

    def search_by_tag(self, tags: List[str], match_all: bool = False) -> List[KnowledgeEntry]:
        """标签搜索"""
        return self._search.tag_search(tags, match_all)

    def search_by_category(self, category: str) -> List[KnowledgeEntry]:
        """分类搜索"""
        return self._search.category_search(category)

    def combined_search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[KnowledgeEntry]:
        """组合搜索"""
        return self._search.combined_search(query, tags, category, limit)

    # ---- 标签与分类 ----

    def get_all_tags(self) -> Set[str]:
        """获取所有标签"""
        return self._indexer.get_all_tags()

    def get_all_categories(self) -> Set[str]:
        """获取所有分类"""
        return self._indexer.get_all_categories()

    # ---- 版本管理 ----

    def get_history(self, entry_id: str) -> List[KnowledgeEntry]:
        """获取条目历史版本"""
        return self._history.get(entry_id, [])

    def rollback(self, entry_id: str, version: int) -> Optional[KnowledgeEntry]:
        """回滚到指定版本"""
        history = self._history.get(entry_id, [])
        for old in history:
            if old.version == version:
                # 保存当前到历史
                current = self._entries.get(entry_id)
                if current:
                    self._history[entry_id].append(
                        KnowledgeEntry.from_dict(current.to_dict())
                    )
                    self._indexer.remove_entry(current)
                # 恢复旧版本
                restored = KnowledgeEntry.from_dict(old.to_dict())
                restored.bump_version()
                self._entries[entry_id] = restored
                self._indexer.index_entry(restored)
                self._save()
                self.logger.info(f"Rolled back entry {entry_id} to version {version} -> {restored.version}")
                return restored
        return None

    # ---- 持久化 ----

    def _save(self) -> None:
        """保存到文件"""
        try:
            self._storage_path.parent.mkdir(exist_ok=True, parents=True)
            data = {
                "entries": {k: v.to_dict() for k, v in self._entries.items()},
                "history": {
                    k: [e.to_dict() for e in v]
                    for k, v in self._history.items()
                },
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save knowledge base: {e}")

    def _load(self) -> None:
        """从文件加载"""
        if not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.get("entries", {}).items():
                entry = KnowledgeEntry.from_dict(v)
                self._entries[k] = entry
                self._indexer.index_entry(entry)
            for k, vlist in data.get("history", {}).items():
                self._history[k] = [KnowledgeEntry.from_dict(v) for v in vlist]
            self.logger.info(f"Loaded {len(self._entries)} entries from {self._storage_path}")
        except Exception as e:
            self.logger.error(f"Failed to load knowledge base: {e}")

    def clear(self) -> None:
        """清空知识库"""
        self._entries.clear()
        self._history.clear()
        self._indexer = KnowledgeIndexer()
        self._search = KnowledgeSearch(self._indexer, self._entries)
        if self._storage_path.exists():
            self._storage_path.unlink()
        self.logger.info("Knowledge base cleared")


# ---- 便捷函数 ----

def create_knowledge_base(storage_path: Optional[Path] = None) -> KnowledgeBase:
    """创建知识库实例"""
    return KnowledgeBase(storage_path)
