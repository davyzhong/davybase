# src/processing_status.py
"""
Davybase 状态追踪系统

统一管理四阶段管线的处理状态：
- IngestStatus: 摄取阶段状态
- DigestStatus: 消化阶段状态
- CompileStatus: 编译阶段状态
- PublishStatus: 发布阶段状态
- PipelineStatus: 完整管线状态快照

设计原则：
1. 幂等性：所有操作前检查状态，避免重复处理
2. 断点续传：支持从中断处恢复
3. 统一接口：各阶段状态管理类接口一致
"""
import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class IngestRecord:
    """摄取记录"""
    note_id: str
    source: str = "getnote"  # getnote|local|pdf
    raw_path: str = ""
    ingested_at: str = ""
    content_hash: str = ""
    error: str = ""


@dataclass
class DigestRecord:
    """消化记录"""
    note_id: str
    source_path: str = ""
    generated_title: str = ""
    recommended_kb: str = ""
    classification_confidence: str = ""
    action: str = ""  # use_existing|create_new
    summarized: bool = False
    classified: bool = False
    moved_to_kb: str = ""
    digested_at: str = ""
    error: str = ""


@dataclass
class CompileRecord:
    """编译记录"""
    wiki_title: str
    source_notes: List[str] = field(default_factory=list)
    wiki_path: str = ""
    compiled_at: str = ""
    provider: str = ""
    error: str = ""


@dataclass
class PublishRecord:
    """发布记录"""
    wiki_title: str
    card_path: str = ""
    published_at: str = ""
    platform: str = ""
    error: str = ""


# =============================================================================
# 抽象基类
# =============================================================================

class ProcessingStatus(ABC):
    """处理状态抽象基类"""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = self._load()

    @abstractmethod
    def _load(self) -> Dict:
        """加载状态数据"""
        pass

    @abstractmethod
    def _save(self):
        """保存状态数据"""
        pass

    @abstractmethod
    def is_processed(self, key: str) -> bool:
        """检查是否已处理"""
        pass

    @abstractmethod
    def mark_processed(self, key: str, data: Dict):
        """标记为已处理"""
        pass

    def get_record(self, key: str) -> Optional[Dict]:
        """获取单条记录"""
        if key in self._data:
            return self._data[key]
        return self._data.get("notes", {}).get(key) or self._data.get("wiki_entries", {}).get(key) or self._data.get("cards", {}).get(key)

    def get_all_records(self) -> Dict[str, Any]:
        """获取所有记录"""
        return self._data

    def get_pending(self, keys: List[str]) -> List[str]:
        """获取待处理的键列表"""
        return [k for k in keys if not self.is_processed(k)]

    def snapshot(self) -> Dict:
        """生成状态快照"""
        return {
            "count": len([k for k, v in self._data.items() if v]),
            "last_updated": self._data.get("last_updated", "")
        }


# =============================================================================
# 摄取状态管理
# =============================================================================

class IngestStatus(ProcessingStatus):
    """摄取阶段状态管理"""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.home() / "ObsidianWiki" / ".davybase" / "progress"
        self.progress_file = state_dir / "ingest.json"
        super().__init__(state_dir)

    def _load(self) -> Dict:
        if self.progress_file.exists():
            try:
                return json.loads(self.progress_file.read_text(encoding='utf-8'))
            except Exception as e:
                return {"notes": {}, "last_updated": datetime.now().isoformat()}
        return {"notes": {}, "last_updated": datetime.now().isoformat()}

    def _save(self):
        self._data["last_updated"] = datetime.now().isoformat()
        self.progress_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def is_processed(self, note_id: str) -> bool:
        """检查笔记是否已摄取"""
        return note_id in self._data.get("notes", {})

    def mark_processed(self, note_id: str, record: IngestRecord):
        """标记笔记为已摄取"""
        self._data.setdefault("notes", {})[note_id] = asdict(record)
        self._save()

    def add_extracted_id(self, note_id: str):
        """添加已抽取 ID（兼容旧格式）"""
        extracted_ids = self._data.setdefault("extracted_ids", [])
        if note_id not in extracted_ids:
            extracted_ids.append(note_id)
            self._save()

    def is_extracted(self, note_id: str) -> bool:
        """检查笔记是否已抽取（兼容旧格式）"""
        return note_id in self._data.get("extracted_ids", []) or self.is_processed(note_id)

    def get_extracted_ids(self) -> Set[str]:
        """获取所有已抽取的笔记 ID"""
        ids = set(self._data.get("extracted_ids", []))
        ids.update(self._data.get("notes", {}).keys())
        return ids

    def snapshot(self) -> Dict:
        """生成摄取状态快照"""
        notes = self._data.get("notes", {})
        extracted_ids = self._data.get("extracted_ids", [])
        total = len(notes) + len(extracted_ids)
        return {
            "total_extracted": total,
            "last_run": self._data.get("last_updated", ""),
            "status": "completed" if total > 0 else "pending"
        }


# =============================================================================
# 消化状态管理
# =============================================================================

class DigestStatus(ProcessingStatus):
    """消化阶段状态管理"""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.home() / "ObsidianWiki" / ".davybase" / "progress"
        self.progress_file = state_dir / "digest.json"
        super().__init__(state_dir)

    def _load(self) -> Dict:
        if self.progress_file.exists():
            try:
                return json.loads(self.progress_file.read_text(encoding='utf-8'))
            except Exception:
                return {"notes": {}, "last_updated": datetime.now().isoformat()}
        return {"notes": {}, "last_updated": datetime.now().isoformat()}

    def _save(self):
        self._data["last_updated"] = datetime.now().isoformat()
        self.progress_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def is_processed(self, note_id: str) -> bool:
        """检查笔记是否已消化"""
        note_data = self._data.get("notes", {}).get(note_id, {})
        return bool(note_data.get("summarized") and note_data.get("classified"))

    def is_summarized(self, note_id: str) -> bool:
        """检查是否已生成标题"""
        return self._data.get("notes", {}).get(note_id, {}).get("summarized", False)

    def is_classified(self, note_id: str) -> bool:
        """检查是否已分类"""
        return self._data.get("notes", {}).get(note_id, {}).get("classified", False)

    def is_moved(self, note_id: str) -> bool:
        """检查是否已移动到知识库"""
        return bool(self._data.get("notes", {}).get(note_id, {}).get("moved_to_kb"))

    def mark_processed(self, note_id: str, record: DigestRecord):
        """标记笔记为已消化"""
        self._data.setdefault("notes", {})[note_id] = asdict(record)
        self._save()

    def mark_summarized(self, note_id: str, title: str):
        """标记为已生成标题"""
        note_data = self._data.setdefault("notes", {}).setdefault(note_id, {})
        note_data["summarized"] = True
        note_data["generated_title"] = title
        note_data["summarized_at"] = datetime.now().isoformat()
        self._save()

    def mark_classified(self, note_id: str, kb: str, action: str, confidence: str):
        """标记为已分类"""
        note_data = self._data.setdefault("notes", {}).setdefault(note_id, {})
        note_data["classified"] = True
        note_data["recommended_kb"] = kb
        note_data["action"] = action
        note_data["classification_confidence"] = confidence
        note_data["classified_at"] = datetime.now().isoformat()
        self._save()

    def mark_moved(self, note_id: str, kb: str):
        """标记为已移动"""
        note_data = self._data.setdefault("notes", {}).setdefault(note_id, {})
        note_data["moved_to_kb"] = kb
        note_data["moved_at"] = datetime.now().isoformat()
        self._save()

    def get_pending_count(self) -> int:
        """获取待处理笔记数量"""
        notes = self._data.get("notes", {})
        return sum(1 for n in notes.values() if not (n.get("summarized") and n.get("classified")))

    def snapshot(self) -> Dict:
        """生成消化状态快照"""
        notes = self._data.get("notes", {})
        return {
            "total_processed": len([n for n in notes.values() if n.get("summarized")]),
            "total_classified": len([n for n in notes.values() if n.get("classified")]),
            "total_moved": len([n for n in notes.values() if n.get("moved_to_kb")]),
            "last_run": self._data.get("last_updated", ""),
            "status": "completed" if notes else "pending"
        }


# =============================================================================
# 编译状态管理
# =============================================================================

class CompileStatus(ProcessingStatus):
    """编译阶段状态管理"""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.home() / "ObsidianWiki" / ".davybase" / "progress"
        self.progress_file = state_dir / "compile.json"
        super().__init__(state_dir)

    def _load(self) -> Dict:
        if self.progress_file.exists():
            try:
                return json.loads(self.progress_file.read_text(encoding='utf-8'))
            except Exception:
                return {"wiki_entries": {}, "last_updated": datetime.now().isoformat()}
        return {"wiki_entries": {}, "last_updated": datetime.now().isoformat()}

    def _save(self):
        self._data["last_updated"] = datetime.now().isoformat()
        self.progress_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def is_processed(self, wiki_title: str) -> bool:
        """检查 Wiki 条目是否已编译"""
        return wiki_title in self._data.get("wiki_entries", {})

    def mark_processed(self, wiki_title: str, record: CompileRecord):
        """标记 Wiki 条目为已编译"""
        self._data.setdefault("wiki_entries", {})[wiki_title] = asdict(record)
        self._save()

    def get_compiled_count(self) -> int:
        """获取已编译的 Wiki 数量"""
        return len(self._data.get("wiki_entries", {}))

    def snapshot(self) -> Dict:
        """生成编译状态快照"""
        entries = self._data.get("wiki_entries", {})
        return {
            "total_wiki_entries": len(entries),
            "last_run": self._data.get("last_updated", ""),
            "status": "completed" if entries else "pending"
        }


# =============================================================================
# 发布状态管理
# =============================================================================

class PublishStatus(ProcessingStatus):
    """发布阶段状态管理"""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.home() / "ObsidianWiki" / ".davybase" / "progress"
        self.progress_file = state_dir / "publish.json"
        super().__init__(state_dir)

    def _load(self) -> Dict:
        if self.progress_file.exists():
            try:
                return json.loads(self.progress_file.read_text(encoding='utf-8'))
            except Exception:
                return {"cards": {}, "last_updated": datetime.now().isoformat()}
        return {"cards": {}, "last_updated": datetime.now().isoformat()}

    def _save(self):
        self._data["last_updated"] = datetime.now().isoformat()
        self.progress_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def is_processed(self, wiki_title: str) -> bool:
        """检查 Wiki 是否已发布"""
        return wiki_title in self._data.get("cards", {})

    def mark_processed(self, wiki_title: str, record: PublishRecord):
        """标记 Wiki 为已发布"""
        self._data.setdefault("cards", {})[wiki_title] = asdict(record)
        self._save()

    def snapshot(self) -> Dict:
        """生成发布状态快照"""
        cards = self._data.get("cards", {})
        return {
            "total_cards": len(cards),
            "last_run": self._data.get("last_updated", ""),
            "status": "completed" if cards else "pending"
        }


# =============================================================================
# 完整管线状态
# =============================================================================

class PipelineStatus:
    """完整管线状态管理器"""

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.home() / "ObsidianWiki" / ".davybase" / "progress"
        self.state_dir = state_dir
        self.ingest = IngestStatus(state_dir)
        self.digest = DigestStatus(state_dir)
        self.compile = CompileStatus(state_dir)
        self.publish = PublishStatus(state_dir)

    def snapshot(self) -> Dict:
        """生成完整管线状态快照"""
        return {
            "ingest": self.ingest.snapshot(),
            "digest": self.digest.snapshot(),
            "compile": self.compile.snapshot(),
            "publish": self.publish.snapshot(),
            "generated_at": datetime.now().isoformat()
        }

    def format_progress(self) -> str:
        """格式化输出当前进度"""
        s = self.snapshot()
        lines = [
            "Davybase 知识生产线状态",
            "=" * 40,
            f"摄取阶段：{s['ingest']['total_extracted']} 条笔记",
            f"消化阶段：{s['digest']['total_processed']} 条已处理，{s['digest']['total_moved']} 条已移动",
            f"编译阶段：{s['compile']['total_wiki_entries']} 个 Wiki 条目",
            f"发布阶段：{s['publish']['total_cards']} 张卡片",
            "=" * 40,
            f"更新时间：{s['generated_at']}"
        ]
        return "\n".join(lines)


# =============================================================================
# 兼容旧系统的 ProcessingStatus 类
# =============================================================================

class LegacyProcessingStatus:
    """兼容旧版 scripts/summarize_and_classify.py 的状态管理类"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.status_file = data_dir / ".processing_status.json"
        self.status: Dict[str, Dict] = self._load_status()

    def _load_status(self) -> Dict:
        """加载处理状态"""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                return {"notes": {}}
        return {"notes": {}}

    def save(self):
        """保存处理状态"""
        self.status["last_updated"] = datetime.now().isoformat()
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)

    def get_note_status(self, note_id: str) -> Dict:
        """获取单个笔记的处理状态"""
        return self.status["notes"].get(note_id, {})

    def is_summarized(self, note_id: str) -> bool:
        """检查是否已生成标题"""
        return self.status["notes"].get(note_id, {}).get("summarized", False)

    def is_classified(self, note_id: str) -> bool:
        """检查是否已分类"""
        return self.status["notes"].get(note_id, {}).get("classified", False)

    def is_moved(self, note_id: str) -> bool:
        """检查是否已移动"""
        return bool(self.status["notes"].get(note_id, {}).get("moved_to_kb"))

    def mark_summarized(self, note_id: str, data: Dict):
        """标记为已生成标题"""
        self.status.setdefault("notes", {}).setdefault(note_id, {}).update(data)
        self.save()

    def mark_classified(self, note_id: str, data: Dict):
        """标记为已分类"""
        self.status.setdefault("notes", {}).setdefault(note_id, {}).update(data)
        self.save()

    def mark_moved(self, note_id: str, data: Dict):
        """标记为已移动"""
        self.status.setdefault("notes", {}).setdefault(note_id, {}).update(data)
        self.save()
