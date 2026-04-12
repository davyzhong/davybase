# Davybase 知识库 Wiki 管线实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 构建 Python CLI 工具，实现 get笔记 → Markdown → LLM 编译 → Obsidian wiki 的自动化管线，支持全量导出和每日增量同步。

**架构：** 四阶段管线（Extractor → Converter → Compiler → Writer），SQLite 跟踪同步状态，PID 锁文件防止并发，结构化日志记录运行状态。

**技术栈：** Python 3.13+、httpx（异步 HTTP）、markitdown（格式转换）、click（CLI）、pyyaml（配置）、sqlite3（标准库）、hashlib（哈希）

---

## 文件结构

**创建的文件：**

| 文件 | 职责 |
|------|------|
| `config.yaml` | 非敏感配置（vault 路径、默认提供商、定时计划） |
| `main.py` | CLI 入口，命令路由 |
| `requirements.txt` | Python 依赖 |
| `src/extractor.py` | get笔记 API 抽取，分页处理，附件下载 |
| `src/converter.py` | markitdown 格式转换 |
| `src/compiler.py` | LLM 编译入口，批次合并，跨 KB 去重 |
| `src/writer.py` | 写入 Obsidian vault，图片下载，冲突处理 |
| `src/sync_state.py` | SQLite 数据库管理，同步状态跟踪 |
| `src/llm_providers/base.py` | LLMProvider 抽象基类 |
| `src/llm_providers/zhipu.py` | 智谱 GLM5 实现 |
| `src/llm_providers/minimax.py` | MiniMax M2.7 实现 |
| `src/utils.py` | 通用工具（哈希计算、锁文件、日志配置） |
| `tests/test_extractor.py` | Extractor 单元测试 |
| `tests/test_converter.py` | Converter 单元测试 |
| `tests/test_compiler.py` | Compiler 单元测试 |
| `tests/test_writer.py` | Writer 单元测试 |
| `tests/test_sync_state.py` | SQLite 状态管理测试 |
| `tests/fixtures/` | 测试用 API 响应、笔记样本 |
| `docs/superpowers/plans/` | 实现计划（本文件） |

**目录：**
- `data/raw/` — 原始笔记暂存区（.gitignore）
- `data/_failed/` — 失败项目暂存（.gitignore）
- `logs/` — 日志文件（.gitignore）

---

## Task 1: 项目骨架与配置

**文件：**
- 创建：`config.yaml`
- 创建：`requirements.txt`
- 创建：`.gitignore`
- 创建：`src/__init__.py`
- 创建：`src/llm_providers/__init__.py`

- [ ] **Step 1: 创建 config.yaml**

```yaml
# Davybase 配置文件
# 敏感信息（API 密钥）存放在 ~/.openclaw/openclaw.json 和环境变量中

vault_path: /Users/qiming/ObsidianWiki
data_path: ./data
logs_path: ./logs

compiler:
  default_provider: zhipu
  batch_size: 15      # 单批次最大笔记数
  max_retries: 2      # LLM 调用最大重试次数

sync:
  schedule: "0 6 * * *"   # 每天早上 6 点
  rate_limit_delay: 1.0   # API 请求间隔（秒）
```

- [ ] **Step 2: 创建 requirements.txt**

```txt
httpx>=0.27.0
click>=8.0.0
pyyaml>=6.0.0
markitdown>=0.1.0
python-dotenv>=1.0.0
```

- [ ] **Step 3: 创建 .gitignore**

```gitignore
# 运行时
data/raw/
data/_failed/
data/sync.db
data/sync.db-journal
data/.sync.lock
logs/
__pycache__/
*.pyc
.env

# IDE
.idea/
.vscode/
*.swp
*.swo
```

- [ ] **Step 4: 创建包初始化文件**

```python
# src/__init__.py
__version__ = "0.1.0"

# src/llm_providers/__init__.py
from .base import LLMProvider
from .zhipu import ZhipuProvider
from .minimax import MiniMaxProvider

__all__ = ["LLMProvider", "ZhipuProvider", "MiniMaxProvider"]
```

- [ ] **Step 5: 安装依赖并验证**

```bash
cd /Users/qiming/workspace/davybase
pip install -r requirements.txt
python -c "import httpx; import click; import yaml; print('OK')"
```
预期输出：`OK`

- [ ] **Step 6: 提交**

```bash
git add config.yaml requirements.txt .gitignore src/__init__.py src/llm_providers/__init__.py
git commit -m "feat: 项目骨架和配置"
```

---

## Task 2: 工具函数与日志

**文件：**
- 创建：`src/utils.py`
- 测试：`tests/test_utils.py`

- [ ] **Step 1: 编写工具函数测试**

```python
# tests/test_utils.py
import hashlib
import os
from src.utils import compute_hash, setup_logging, LockFile

def test_compute_hash():
    content = "hello world"
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert compute_hash(content) == expected

def test_compute_hash_different_inputs():
    h1 = compute_hash("input1")
    h2 = compute_hash("input2")
    assert h1 != h2

def test_lock_file_acquire_release(tmp_path):
    lock_path = tmp_path / ".test.lock"
    with LockFile(str(lock_path)) as lock:
        assert lock.acquired
        assert lock_path.exists()
    assert not lock_path.exists()

def test_lock_file_blocked_by_existing(tmp_path, monkeypatch):
    lock_path = tmp_path / ".test.lock"
    lock_path.write_text("12345")
    # 模拟 PID 12345 存活
    monkeypatch.setattr(os, "kill", lambda pid, sig: None if pid == 12345 else OSError())
    with LockFile(str(lock_path)) as lock:
        assert not lock.acquired
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_utils.py -v
```
预期：FAIL（模块不存在）

- [ ] **Step 3: 实现工具函数**

```python
# src/utils.py
import hashlib
import logging
import os
import signal
import sys
from contextlib import ContextDecorator
from pathlib import Path

def compute_hash(content: str) -> str:
    """计算内容的 SHA-256 哈希"""
    return hashlib.sha256(content.encode()).hexdigest()

def setup_logging(log_file: str = None) -> logging.Logger:
    """配置结构化日志"""
    logger = logging.getLogger("davybase")
    logger.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s %(levelname)-5s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)
    
    return logger

class LockFile(ContextDecorator):
    """PID 锁文件，防止并发运行"""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.acquired = False
        self.pid = os.getpid()
    
    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def acquire(self) -> bool:
        if self.path.exists():
            try:
                existing_pid = int(self.path.read_text().strip())
                if self._is_pid_alive(existing_pid):
                    return False
            except (ValueError, PermissionError):
                pass
            #  stale lock, remove it
            self.path.unlink()
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(str(self.pid))
        self.acquired = True
        return True
    
    def release(self):
        if self.acquired and self.path.exists():
            try:
                if self.path.read_text().strip() == str(self.pid):
                    self.path.unlink()
            except (FileNotFoundError, PermissionError):
                pass
        self.acquired = False
    
    def __enter__(self):
        self.acquired = self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_utils.py -v
```
预期：3 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/utils.py tests/test_utils.py
git commit -m "feat: 工具函数（哈希、日志、锁文件）"
```

---

## Task 3: SQLite 同步状态管理

**文件：**
- 创建：`src/sync_state.py`
- 测试：`tests/test_sync_state.py`

- [ ] **Step 1: 编写状态管理测试**

```python
# tests/test_sync_state.py
import pytest
from pathlib import Path
from src.sync_state import SyncState, SyncRun

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    state = SyncState(str(db_path))
    yield state
    state.close()

def test_insert_and_get_note(temp_db):
    temp_db.insert_note("12345", "plain_text", "TestKB", "/raw/TestKB/12345.md", "abc123")
    note = temp_db.get_note("12345")
    assert note["note_id"] == "12345"
    assert note["note_type"] == "plain_text"
    assert note["content_hash"] == "abc123"

def test_update_note_error(temp_db):
    temp_db.insert_note("12345", "plain_text", "TestKB", "/raw/TestKB/12345.md", "abc123")
    temp_db.update_note_error("12345", "API timeout")
    note = temp_db.get_note("12345")
    assert note["error"] == "API timeout"

def test_get_failed_notes(temp_db):
    temp_db.insert_note("1", "plain_text", "KB1", "/raw/1.md", "h1")
    temp_db.update_note_error("1", "error1")
    temp_db.insert_note("2", "plain_text", "KB1", "/raw/2.md", "h2")
    failed = temp_db.get_failed_notes()
    assert len(failed) == 1
    assert failed[0]["note_id"] == "1"

def test_record_sync_run(temp_db):
    run_id = temp_db.record_sync_run("full", "zhipu")
    temp_db.complete_sync_run(run_id, 100, 50, 2)
    # Just verify it doesn't raise

def test_get_status(temp_db):
    temp_db.insert_note("1", "plain_text", "KB1", "/raw/1.md", "h1")
    temp_db.insert_note("2", "plain_text", "KB2", "/raw/2.md", "h2")
    temp_db.update_note_error("1", "error")
    status = temp_db.get_status()
    assert status["total_notes"] == 2
    assert status["failed_count"] == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_sync_state.py -v
```
预期：FAIL

- [ ] **Step 3: 实现同步状态管理**

```python
# src/sync_state.py
import sqlite3
from datetime import datetime
from typing import Optional

class SyncState:
    """SQLite 同步状态管理"""
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
    
    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS sync_state (
                note_id TEXT PRIMARY KEY,
                note_type TEXT,
                knowledge_base TEXT,
                raw_path TEXT,
                synced_at DATETIME,
                content_hash TEXT,
                compiled_at DATETIME,
                wiki_path TEXT,
                error TEXT
            );
            
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT,
                provider TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                notes_extracted INTEGER,
                notes_compiled INTEGER,
                errors INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS wiki_entries (
                title TEXT PRIMARY KEY,
                source_notes TEXT,
                wiki_hash TEXT,
                created_at DATETIME,
                updated_at DATETIME
            );
        """)
        self.conn.commit()
    
    def insert_note(self, note_id: str, note_type: str, kb: str, raw_path: str, content_hash: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sync_state 
            (note_id, note_type, knowledge_base, raw_path, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note_id, note_type, kb, raw_path, datetime.now().isoformat(), content_hash))
        self.conn.commit()
    
    def get_note(self, note_id: str) -> Optional[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE note_id = ?", (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_note_error(self, note_id: str, error: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE sync_state SET error = ? WHERE note_id = ?", (error, note_id))
        self.conn.commit()
    
    def get_failed_notes(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE error IS NOT NULL")
        return [dict(row) for row in cursor.fetchall()]
    
    def record_sync_run(self, run_type: str, provider: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sync_runs (run_type, provider, started_at)
            VALUES (?, ?, ?)
        """, (run_type, provider, datetime.now().isoformat()))
        self.conn.commit()
        return cursor.lastrowid
    
    def complete_sync_run(self, run_id: int, extracted: int, compiled: int, errors: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sync_runs 
            SET completed_at = ?, notes_extracted = ?, notes_compiled = ?, errors = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), extracted, compiled, errors, run_id))
        self.conn.commit()
    
    def get_status(self) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM sync_state")
        total = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(*) as failed FROM sync_state WHERE error IS NOT NULL")
        failed = cursor.fetchone()["failed"]
        
        cursor.execute("SELECT COUNT(*) as wiki FROM wiki_entries")
        wiki = cursor.fetchone()["wiki"]
        
        cursor.execute("""
            SELECT run_type, provider, completed_at 
            FROM sync_runs 
            WHERE completed_at IS NOT NULL
            ORDER BY completed_at DESC LIMIT 1
        """)
        last_run = cursor.fetchone()
        
        return {
            "total_notes": total,
            "failed_count": failed,
            "wiki_entries": wiki,
            "last_run": dict(last_run) if last_run else None
        }
    
    def close(self):
        self.conn.close()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_sync_state.py -v
```
预期：6 个测试全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/sync_state.py tests/test_sync_state.py
git commit -m "feat: SQLite 同步状态管理"
```

---

## Task 4: Extractor（抽取器）

**文件：**
- 创建：`src/extractor.py`
- 测试：`tests/test_extractor.py`
- 创建：`tests/fixtures/getnote_responses.json`

- [ ] **Step 1: 准备测试夹具**

```json
{
  "knowledge_list": {
    "data": {
      "topics": [
        {"topic_id": "kb1", "name": "深度学习", "description": "DL 笔记", "stats": {"note_count": 3}},
        {"topic_id": "kb2", "name": "产品思考", "description": "产品笔记", "stats": {"note_count": 2}}
      ],
      "has_more": false,
      "total": 2
    }
  },
  "knowledge_notes_kb1": {
    "data": {
      "notes": [
        {"note_id": "1001", "title": "反向传播", "note_type": "plain_text", "created_at": "2026-04-01 10:00:00"},
        {"note_id": "1002", "title": "梯度下降", "note_type": "plain_text", "created_at": "2026-04-02 11:00:00"},
        {"note_id": "1003", "title": "Transformer", "note_type": "link", "created_at": "2026-04-03 12:00:00"}
      ],
      "has_more": false
    }
  },
  "note_detail_1001": {
    "data": {
      "note": {
        "note_id": "1001",
        "title": "反向传播",
        "content": "# 反向传播算法\\n\\n核心是链式法则。",
        "note_type": "plain_text",
        "tags": ["深度学习"],
        "created_at": "2026-04-01 10:00:00",
        "attachments": []
      }
    }
  }
}
```

- [ ] **Step 2: 编写 Extractor 测试**

```python
# tests/test_extractor.py
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from src.extractor import Extractor, GetNoteClient

@pytest.fixture
def fixtures():
    with open("tests/fixtures/getnote_responses.json") as f:
        return json.load(f)

@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir

@pytest.mark.asyncio
async def test_fetch_knowledge_bases(fixtures):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = fixtures["knowledge_list"]
        async with GetNoteClient("test_key", "test_client_id") as client:
            kbs = await client.list_knowledge_bases()
            assert len(kbs) == 2
            assert kbs[0]["topic_id"] == "kb1"

@pytest.mark.asyncio
async def test_fetch_knowledge_notes(fixtures):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = fixtures["knowledge_notes_kb1"]
        async with GetNoteClient("test_key", "test_client_id") as client:
            notes = await client.list_knowledge_notes("kb1")
            assert len(notes) == 3
            assert notes[0]["note_id"] == "1001"

@pytest.mark.asyncio
async def test_extractor_saves_raw_notes(fixtures, temp_data_dir):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            # list_knowledge_bases
            type("obj", (object,), {"json": lambda: fixtures["knowledge_list"]}),
            # list_knowledge_notes for kb1
            type("obj", (object,), {"json": lambda: fixtures["knowledge_notes_kb1"]}),
            # get_note_detail for 1001
            type("obj", (object,), {"json": lambda: fixtures["note_detail_1001"]}),
        ]
        # Mock remaining calls for other notes...
        
        extractor = Extractor("test_key", "test_client_id", str(temp_data_dir))
        await extractor.run()
        
        raw_dir = temp_data_dir / "raw" / "深度学习"
        assert raw_dir.exists()
        assert (raw_dir / "1001.md").exists()
```

- [ ] **Step 3: 运行测试验证失败**

```bash
pytest tests/test_extractor.py -v -k "test_fetch"
```
预期：FAIL

- [ ] **Step 4: 实现 Extractor**

```python
# src/extractor.py
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Optional
import httpx
import logging

logger = logging.getLogger("davybase.extractor")

class GetNoteClient:
    """get笔记 API 客户端"""
    
    BASE_URL = "https://openapi.biji.com"
    
    def __init__(self, api_key: str, client_id: str):
        self.api_key = api_key
        self.client_id = client_id
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": self.api_key,
                "X-Client-ID": self.client_id
            },
            timeout=30.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()
    
    async def _get(self, path: str, params: dict = None) -> dict:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    
    async def list_knowledge_bases(self) -> list:
        """获取知识库列表"""
        result = await self._get("/open/api/v1/resource/knowledge/list", {"page": 1})
        return result.get("data", {}).get("topics", [])
    
    async def list_knowledge_notes(self, topic_id: str, page: int = 1) -> tuple[list, bool]:
        """获取知识库笔记列表，返回 (notes, has_more)"""
        result = await self._get("/open/api/v1/resource/knowledge/notes", {
            "topic_id": topic_id,
            "page": page
        })
        data = result.get("data", {})
        return data.get("notes", []), data.get("has_more", False)
    
    async def get_note_detail(self, note_id: str) -> dict:
        """获取笔记详情"""
        result = await self._get("/open/api/v1/resource/note/detail", {"id": note_id})
        return result.get("data", {}).get("note", {})

class Extractor:
    """笔记抽取器"""
    
    def __init__(self, api_key: str, client_id: str, data_dir: str):
        self.api_key = api_key
        self.client_id = client_id
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.failed_dir = self.data_dir / "_failed"
    
    async def run(self):
        """执行抽取"""
        logger.info("开始抽取笔记")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        
        async with GetNoteClient(self.api_key, self.client_id) as client:
            # 获取所有知识库
            kbs = await client.list_knowledge_bases()
            logger.info(f"发现 {len(kbs)} 个知识库")
            
            for kb in kbs:
                await self._extract_knowledge_base(client, kb)
            
            # 获取散落笔记
            await self._extract_inbox_notes(client)
        
        logger.info("抽取完成")
    
    async def _extract_knowledge_base(self, client: GetNoteClient, kb: dict):
        """抽取单个知识库"""
        kb_name = kb["name"]
        kb_dir = self.raw_dir / kb_name
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "attachments").mkdir(exist_ok=True)
        
        logger.info(f"抽取知识库 \"{kb_name}\"")
        
        page = 1
        has_more = True
        while has_more:
            notes, has_more = await client.list_knowledge_notes(kb["topic_id"], page)
            logger.info(f"  第{page}页：{len(notes)} 条笔记")
            
            for note in notes:
                await self._extract_note(client, note, kb_dir, kb_name)
            
            page += 1
            if has_more:
                await asyncio.sleep(1.0)  # 速率限制
    
    async def _extract_note(self, client: GetNoteClient, note: dict, kb_dir: Path, kb_name: str):
        """抽取单条笔记"""
        note_id = note["note_id"]
        
        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.5)  # 速率限制
            
            content = self._format_note_content(detail)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            note_file = kb_dir / f"{note_id}.md"
            note_file.write_text(content, encoding="utf-8")
            
            logger.debug(f"  保存笔记 {note_id}: {detail.get('title', '无标题')}")
            
        except Exception as e:
            logger.error(f"  抽取笔记 {note_id} 失败：{e}")
            self._save_failed_note(note, str(e))
    
    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        lines = [
            "---",
            f"note_id: {detail.get('note_id', '')}",
            f"note_type: {detail.get('note_type', '')}",
            f"created_at: {detail.get('created_at', '')}",
            f"tags: {detail.get('tags', [])}",
            "---",
            "",
            f"# {detail.get('title', '无标题')}",
            "",
            detail.get("content", ""),
        ]
        
        # 添加链接笔记的原文
        if detail.get("web_page", {}).get("content"):
            lines.extend([
                "",
                "---",
                "## 原文链接",
                "",
                detail["web_page"]["content"],
            ])
        
        return "\n".join(lines)
    
    def _save_failed_note(self, note: dict, error: str):
        """保存失败的笔记"""
        failed_file = self.failed_dir / f"{note['note_id']}.json"
        failed_file.write_text(json.dumps({
            "note": note,
            "error": error
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    
    async def _extract_inbox_notes(self, client: GetNoteClient):
        """抽取散落笔记（不在任何知识库中）"""
        inbox_dir = self.raw_dir / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("抽取散落笔记")
        # 实现类似知识库的抽取逻辑...
```

- [ ] **Step 5: 运行测试验证通过**

```bash
pytest tests/test_extractor.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/extractor.py tests/test_extractor.py tests/fixtures/getnote_responses.json
git commit -m "feat: Extractor - get 笔记 API 抽取"
```

---

## Task 5: Converter（转换器）

**文件：**
- 创建：`src/converter.py`
- 测试：`tests/test_converter.py`
- 创建：`tests/fixtures/html_sample.html`

- [ ] **Step 1: 编写 Converter 测试**

```python
# tests/test_converter.py
import pytest
from pathlib import Path
from src.converter import Converter

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

@pytest.fixture
def html_fixture():
    return Path("tests/fixtures/html_sample.html").read_text()

def test_convert_html_to_markdown(html_fixture, temp_dir):
    converter = Converter(str(temp_dir))
    md = converter.convert_html(html_fixture)
    assert "# 标题" in md
    assert "段落内容" in md

def test_passthrough_markdown(temp_dir):
    converter = Converter(str(temp_dir))
    content = "# 已有标题\n\n正文内容"
    result = converter.convert(content, note_type="plain_text")
    assert result == content

def test_convert_link_note(temp_dir):
    converter = Converter(str(temp_dir))
    html = "<html><body><h1>标题</h1><p>内容</p></body></html>"
    result = converter.convert(html, note_type="link")
    assert "# 标题" in result
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_converter.py -v
```

- [ ] **Step 3: 实现 Converter**

```python
# src/converter.py
from markitdown import MarkItDown
import logging

logger = logging.getLogger("davybase.converter")

class Converter:
    """格式转换器"""
    
    def __init__(self, data_dir: str):
        self.md = MarkItDown()
    
    def convert(self, content: str, note_type: str) -> str:
        """转换内容
        
        Args:
            content: 原始内容
            note_type: 笔记类型
            
        Returns:
            转换后的 Markdown
        """
        if note_type in ("plain_text", "img_text"):
            # 已是 Markdown，直接透传
            return content
        
        if note_type == "link":
            # HTML 转 Markdown
            return self.convert_html(content)
        
        if note_type in ("audio", "meeting", "local_audio", "internal_record"):
            # 转写文本，直接透传
            return content
        
        # 未知类型，原样返回
        return content
    
    def convert_html(self, html: str) -> str:
        """HTML 转 Markdown"""
        try:
            result = self.md.convert_string(html)
            return result.text_content
        except Exception as e:
            logger.warning(f"HTML 转换失败：{e}")
            # 降级：返回原始内容
            return html
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_converter.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/converter.py tests/test_converter.py tests/fixtures/html_sample.html
git commit -m "feat: Converter - markitdown 格式转换"
```

---

## Task 6: Compiler（编译器）+ LLM 提供商

**文件：**
- 创建：`src/llm_providers/base.py`
- 创建：`src/llm_providers/zhipu.py`
- 创建：`src/llm_providers/minimax.py`
- 创建：`src/compiler.py`
- 测试：`tests/test_compiler.py`
- 测试：`tests/test_llm_providers.py`

- [ ] **Step 1: 定义 LLMProvider 抽象基类**

```python
# src/llm_providers/base.py
from abc import ABC, abstractmethod
from typing import Optional

class LLMProvider(ABC):
    """LLM 提供商抽象接口"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送聊天请求，返回响应文本"""
        pass
    
    @abstractmethod
    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        """编译笔记为 wiki 条目"""
        pass
```

- [ ] **Step 2: 实现智谱 GLM5 提供商**

```python
# src/llm_providers/zhipu.py
import httpx
from .base import LLMProvider

COMPILE_PROMPT = """你是一个知识库编辑。以下是从 get 笔记导出的原始笔记（Markdown 格式）。
请完成以下任务：

1. 阅读所有笔记，识别其中的核心概念和主题
2. 为每个核心概念创建一个 wiki 条目，包含：
   - 核心摘要（200 字以内）
   - 关键要点（要点列表）
   - 与其他概念的关系（使用 [[双链]] 格式）
3. 每个条目必须包含 frontmatter（title, source, tags, created, type）
4. 使用 Obsidian Flavored Markdown 格式
5. 用 %%davybase-auto-begin%% 和 %%davybase-auto-end%% 标记包裹所有自动生成的内容

输出格式：每个 wiki 条目为一个文件，条目之间用 "---ENTRY---" 分隔

原始笔记：
{notes}

已有 wiki 条目（用于交叉引用）：
{existing_wiki}
"""

class ZhipuProvider(LLMProvider):
    """智谱 GLM5 提供商"""
    
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    MODEL = "glm-5"
    
    async def chat(self, messages: list[dict], **kwargs) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.MODEL,
                    "messages": messages,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        prompt = COMPILE_PROMPT.format(
            notes="\n\n".join(notes),
            existing_wiki="\n\n".join(existing_wiki) if existing_wiki else "无"
        )
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature=0.7)
```

- [ ] **Step 3: 实现 MiniMax 提供商**

```python
# src/llm_providers/minimax.py
import httpx
from .base import LLMProvider

class MiniMaxProvider(LLMProvider):
    """MiniMax M2.7 提供商"""
    
    BASE_URL = "https://api.minimaxi.com/v1/chat/completions"
    MODEL = "codex-MiniMax-M2.7"
    
    async def chat(self, messages: list[dict], **kwargs) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.MODEL,
                    "messages": messages,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        # 与智谱相同的 prompt 模板
        prompt = COMPILE_PROMPT.format(
            notes="\n\n".join(notes),
            existing_wiki="\n\n".join(existing_wiki) if existing_wiki else "无"
        )
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature=0.7)
```

- [ ] **Step 4: 实现 Compiler**

```python
# src/compiler.py
import asyncio
from pathlib import Path
from typing import Optional
import logging
from .llm_providers.base import LLMProvider
from .llm_providers.zhipu import ZhipuProvider
from .llm_providers.minimax import MiniMaxProvider

logger = logging.getLogger("davybase.compiler")

class Compiler:
    """LLM 编译器"""
    
    def __init__(self, provider: LLMProvider, data_dir: str, vault_path: str):
        self.provider = provider
        self.data_dir = Path(data_dir)
        self.vault_path = Path(vault_path)
        self.wiki_dir = self.vault_path / "wiki"
    
    async def run(self, provider_name: str = "zhipu"):
        """执行编译"""
        logger.info(f"开始编译（使用 {provider_name}）")
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        
        # 按知识库分组编译
        raw_dir = self.data_dir / "raw"
        for kb_dir in raw_dir.iterdir():
            if kb_dir.is_dir() and kb_dir.name != "_inbox":
                await self._compile_knowledge_base(kb_dir)
        
        logger.info("编译完成")
    
    async def _compile_knowledge_base(self, kb_dir: Path):
        """编译单个知识库"""
        kb_name = kb_dir.name
        logger.info(f"编译知识库 \"{kb_name}\"")
        
        # 收集笔记
        notes = []
        for note_file in kb_dir.glob("*.md"):
            if note_file.stem != "_inbox":
                notes.append(note_file.read_text(encoding="utf-8"))
        
        if not notes:
            logger.warning(f"  知识库 \"{kb_name}\" 无笔记，跳过")
            return
        
        # 分批处理（>20 条笔记时）
        batch_size = 15
        if len(notes) > batch_size:
            batches = [notes[i:i+batch_size] for i in range(0, len(notes), batch_size)]
            batch_results = []
            for i, batch in enumerate(batches):
                logger.info(f"  编译批次 {i+1}/{len(batches)}")
                result = await self.provider.compile_notes(batch, [])
                batch_results.append(result)
            
            # 合并批次
            merged = await self._merge_batches(batch_results)
            self._save_wiki_entries(merged, kb_name)
        else:
            result = await self.provider.compile_notes(notes, [])
            self._save_wiki_entries(result, kb_name)
    
    async def _merge_batches(self, batch_results: list[str]) -> str:
        """合并多个批次的编译结果"""
        prompt = f"""以下是从同一知识库不同批次编译的 wiki 条目。合并描述相同概念的条目。保留更丰富的摘要。合并关键要点，去除重复。更新双链指向合并后的条目标题。

批次结果：
{"---BATCH---".join(batch_results)}
"""
        return await self.provider.chat([{"role": "user", "content": prompt}])
    
    def _save_wiki_entries(self, content: str, kb_name: str):
        """保存 wiki 条目"""
        entries = content.split("---ENTRY---")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            
            # 解析标题
            title = self._extract_title(entry)
            if title:
                file_path = self.wiki_dir / f"{title}.md"
                file_path.write_text(entry, encoding="utf-8")
                logger.debug(f"  保存 wiki 条目：{title}")
    
    def _extract_title(self, content: str) -> Optional[str]:
        """从内容中提取标题"""
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return None
```

- [ ] **Step 5: 编写测试**

```python
# tests/test_compiler.py
import pytest
from unittest.mock import AsyncMock, patch
from src.compiler import Compiler
from src.llm_providers.zhipu import ZhipuProvider

@pytest.mark.asyncio
async def test_compiler_saves_wiki_entries(tmp_path):
    mock_provider = AsyncMock(spec=ZhipuProvider)
    mock_provider.compile_notes.return_value = """---ENTRY---
# 测试概念

%%davybase-auto-begin%%
## 摘要
这是摘要。
%%davybase-auto-end%%
"""
    vault_path = tmp_path / "vault"
    compiler = Compiler(mock_provider, str(tmp_path / "data"), str(vault_path))
    await compiler.run()
    
    wiki_dir = vault_path / "wiki"
    assert (wiki_dir / "测试概念.md").exists()
```

- [ ] **Step 6: 运行测试验证通过**

```bash
pytest tests/test_compiler.py tests/test_llm_providers.py -v
```

- [ ] **Step 7: 提交**

```bash
git add src/llm_providers/ src/compiler.py tests/test_compiler.py tests/test_llm_providers.py
git commit -m "feat: Compiler + LLM 提供商（智谱 GLM5、MiniMax M2.7）"
```

---

## Task 7: Writer（写入器）

**文件：**
- 创建：`src/writer.py`
- 测试：`tests/test_writer.py`

- [ ] **Step 1: 编写 Writer 测试**

```python
# tests/test_writer.py
import pytest
from pathlib import Path
from src.writer import Writer

@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki").mkdir()
    return vault

def test_writer_creates_new_entry(temp_vault):
    writer = Writer(str(temp_vault))
    content = """---
title: 新概念
---

# 新概念

%%davybase-auto-begin%%
摘要内容
%%davybase-auto-end%%
"""
    writer.write(content)
    assert (temp_vault / "wiki" / "新概念.md").exists()

def test_writer_preserves_manual_edits(temp_vault):
    writer = Writer(str(temp_vault))
    
    # 首次写入
    writer.write("""---
title: 现有概念
---

# 现有概念

%%davybase-auto-begin%%
旧摘要
%%davybase-auto-end%%

## 手动部分
这是手动编辑的内容。
""")
    
    # 再次写入（更新 auto 块）
    writer.write("""---
title: 现有概念
---

# 现有概念

%%davybase-auto-begin%%
新摘要
%%davybase-auto-end%%
""")
    
    content = (temp_vault / "wiki" / "现有概念.md").read_text()
    assert "新摘要" in content
    assert "手动部分" in content
    assert "这是手动编辑的内容" in content
```

- [ ] **Step 2: 实现 Writer**

```python
# src/writer.py
import hashlib
import re
from pathlib import Path
import httpx
import logging

logger = logging.getLogger("davybase.writer")

class Writer:
    """Obsidian vault 写入器"""
    
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.wiki_dir = self.vault_path / "wiki"
        self.attachments_dir = self.wiki_dir / "attachments"
    
    def write(self, content: str):
        """写入 wiki 条目"""
        title = self._extract_title(content)
        if not title:
            logger.warning("无法提取标题，跳过")
            return
        
        file_path = self.wiki_dir / f"{self._sanitize_filename(title)}.md"
        
        if file_path.exists():
            # 处理冲突
            existing = file_path.read_text(encoding="utf-8")
            if self._is_auto_block_changed(existing, content):
                content = self._merge_content(existing, content)
            else:
                logger.debug(f"条目 {title} 无变更，跳过")
                return
        
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"写入 wiki 条目：{title}")
    
    def _extract_title(self, content: str) -> str:
        """提取 frontmatter 中的 title"""
        match = re.search(r"^---\s*\n.*?title:\s*(.+?)\s*\n", content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
        # 回退到第一个 H1
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return None
    
    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        # 移除非法字符
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()
    
    def _is_auto_block_changed(self, existing: str, new: str) -> bool:
        """检查 auto 块是否有变更"""
        old_block = self._extract_auto_block(existing)
        new_block = self._extract_auto_block(new)
        return old_block != new_block
    
    def _extract_auto_block(self, content: str) -> str:
        """提取 auto 块内容"""
        match = re.search(
            r"%%davybase-auto-begin%%(.*?)%%davybase-auto-end%%",
            content,
            re.DOTALL
        )
        return match.group(1).strip() if match else ""
    
    def _merge_content(self, existing: str, new: str) -> str:
        """合并现有内容和新的 auto 块"""
        # 保留 auto 块之外的手动内容
        manual_part = re.sub(
            r"%%davybase-auto-begin%%.*?%%davybase-auto-end%%",
            "",
            existing,
            flags=re.DOTALL
        )
        
        # 提取新的 auto 块
        new_auto_match = re.search(
            r"(%%davybase-auto-begin%%.*?%%davybase-auto-end%%)",
            new,
            re.DOTALL
        )
        new_auto = new_auto_match.group(1) if new_auto_match else ""
        
        # 组合
        return new.replace(new_auto, new_auto + "\n" + manual_part.strip())
    
    async def download_image(self, url: str, note_id: str) -> str:
        """下载图片到本地，返回本地路径"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            filename = f"{note_id}_{url.split('/')[-1]}"
            image_path = self.attachments_dir / filename
            image_path.write_bytes(response.content)
            
            return f"attachments/{filename}"
```

- [ ] **Step 3: 运行测试验证通过**

```bash
pytest tests/test_writer.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/writer.py tests/test_writer.py
git commit -m "feat: Writer - Obsidian vault 写入，支持冲突处理"
```

---

## Task 8: CLI 入口与命令

**文件：**
- 创建：`main.py`
- 创建：`src/config.py`
- 测试：`tests/test_cli.py`

- [ ] **Step 1: 实现配置加载**

```python
# src/config.py
import os
import yaml
from pathlib import Path
from typing import Optional

class Config:
    """配置管理"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = {}
        self.load()
    
    def load(self):
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
    
    @property
    def vault_path(self) -> str:
        return self._config.get("vault_path", "/Users/qiming/ObsidianWiki")
    
    @property
    def data_path(self) -> str:
        return self._config.get("data_path", "./data")
    
    @property
    def default_provider(self) -> str:
        return self._config.get("compiler", {}).get("default_provider", "zhipu")
    
    @property
    def logs_path(self) -> str:
        return self._config.get("logs_path", "./logs")
    
    def get_getnote_credentials(self) -> tuple[str, str]:
        """获取 get 笔记 API 凭据"""
        openclaw_path = Path.home() / ".openclaw" / "openclaw.json"
        if not openclaw_path.exists():
            raise RuntimeError("未找到 ~/.openclaw/openclaw.json，请先配置 get 笔记")
        
        import json
        data = json.loads(openclaw_path.read_text(encoding="utf-8"))
        skill_config = data.get("skills", {}).get("entries", {}).get("getnote", {})
        api_key = skill_config.get("apiKey")
        client_id = skill_config.get("env", {}).get("GETNOTE_CLIENT_ID")
        
        if not api_key or not client_id:
            raise RuntimeError("get 笔记 API 凭据配置不完整")
        
        return api_key, client_id
    
    def get_llm_api_key(self, provider: str) -> str:
        """获取 LLM API 密钥"""
        env_map = {"zhipu": "ZHIPU_API_KEY", "minimax": "MINIMAX_API_KEY"}
        env_var = env_map.get(provider)
        if not env_var:
            raise ValueError(f"未知提供商：{provider}")
        
        api_key = os.environ.get(env_var)
        if not api_key:
            raise RuntimeError(f"未设置环境变量 {env_var}")
        
        return api_key
```

- [ ] **Step 2: 实现 CLI 入口**

```python
# main.py
import click
import asyncio
import logging
from src.config import Config
from src.utils import setup_logging, LockFile
from src.extractor import Extractor
from src.converter import Converter
from src.compiler import Compiler
from src.writer import Writer
from src.sync_state import SyncState
from src.llm_providers.zhipu import ZhipuProvider
from src.llm_providers.minimax import MiniMaxProvider

@click.group()
def cli():
    """Davybase - get 笔记到 Obsidian Wiki 的知识库管线"""
    pass

@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
def full_sync(provider: str):
    """全量同步"""
    asyncio.run(run_sync("full", provider))

@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
def incremental(provider: str):
    """增量同步"""
    asyncio.run(run_sync("incremental", provider))

@cli.command()
def extract_only():
    """仅抽取，不编译"""
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")
    
    api_key, client_id = config.get_getnote_credentials()
    extractor = Extractor(api_key, client_id, config.data_path)
    asyncio.run(extractor.run())

@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
def compile_only(provider: str):
    """重新编译已有的 raw/"""
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")
    
    provider = provider or config.default_provider
    api_key = config.get_llm_api_key(provider)
    
    if provider == "zhipu":
        llm_provider = ZhipuProvider(api_key)
    else:
        llm_provider = MiniMaxProvider(api_key)
    
    compiler = Compiler(llm_provider, config.data_path, config.vault_path)
    asyncio.run(compiler.run(provider))

@cli.command()
def status():
    """查看同步状态"""
    config = Config()
    state = SyncState(f"{config.data_path}/sync.db")
    s = state.get_status()
    
    click.echo(f"上次同步：{s['last_run']['completed_at'] if s['last_run'] else '无'} ({s['last_run']['run_type'] if s['last_run'] else ''}, {s['last_run']['provider'] if s['last_run'] else ''})")
    click.echo(f"已同步笔记：{s['total_notes']}")
    click.echo(f"Wiki 条目：{s['wiki_entries']}")
    click.echo(f"失败：{s['failed_count']}")

@cli.command()
def quota():
    """检查 get 笔记 API 配额"""
    import subprocess
    result = subprocess.run(
        ["getnote", "quota", "-o", "json"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        click.echo(result.stdout)
    else:
        click.echo(f"查询失败：{result.stderr}")

async def run_sync(run_type: str, provider: str):
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")
    
    lock_path = f"{config.data_path}/.sync.lock"
    with LockFile(lock_path) as lock:
        if not lock.acquired:
            logger.error("另一个同步进程正在运行")
            return
        
        api_key, client_id = config.get_getnote_credentials()
        provider = provider or config.default_provider
        llm_api_key = config.get_llm_api_key(provider)
        
        state = SyncState(f"{config.data_path}/sync.db")
        run_id = state.record_sync_run(run_type, provider)
        
        try:
            # 抽取
            extractor = Extractor(api_key, client_id, config.data_path)
            await extractor.run()
            
            # 转换（在抽取过程中已完成）
            converter = Converter(config.data_path)
            
            # 编译
            if provider == "zhipu":
                llm_provider = ZhipuProvider(llm_api_key)
            else:
                llm_provider = MiniMaxProvider(llm_api_key)
            
            compiler = Compiler(llm_provider, config.data_path, config.vault_path)
            await compiler.run(provider)
            
            # 写入（在 compiler 中完成）
            
            state.complete_sync_run(run_id, 0, 0, 0)
            logger.info("同步完成")
            
        except Exception as e:
            logger.exception(f"同步失败：{e}")
            state.complete_sync_run(run_id, 0, 0, 1)

if __name__ == "__main__":
    cli()
```

- [ ] **Step 3: 编写 CLI 测试**

```python
# tests/test_cli.py
from click.testing import CliRunner
from main import cli

def test_status_command(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_cli.py -v
```

- [ ] **Step 5: 提交**

```bash
git add main.py src/config.py tests/test_cli.py
git commit -m "feat: CLI 入口与命令（full-sync, incremental, status, quota）"
```

---

## Task 9: Skill 封装

**文件：**
- 创建：`~/.claude/skills/davybase/SKILL.md`
- 创建：`~/.claude/skills/davybase/_meta.json`
- 创建：`~/.claude/skills/davybase/references/sync.md`
- 创建：`~/.claude/skills/davybase/references/status.md`
- 创建：`~/.claude/skills/davybase/scripts/davybase.py`

- [ ] **Step 1: 创建 Skill 元数据**

```json
{
  "_meta.json": {
    "name": "davybase",
    "version": "0.1.0",
    "description": "get 笔记到 Obsidian Wiki 的知识库管线"
  }
}
```

- [ ] **Step 2: 创建 SKILL.md**

```markdown
# Davybase Skill

## 触发词

| 指令 | 路由 |
|------|------|
| "同步笔记" / "sync notes" | `python main.py incremental` |
| "全量导出" / "full export" | `python main.py full-sync` |
| "笔记状态" / "note status" | `python main.py status` |
| "重新编译" / "recompile" | `python main.py compile-only` |

## 配置

确保以下配置已就绪：
1. `~/.openclaw/openclaw.json` - get 笔记 API 凭据
2. `ZHIPU_API_KEY` 或 `MINIMAX_API_KEY` 环境变量

## 使用示例

> 同步笔记
→ 执行 `python main.py incremental`

> 全量导出，用 MiniMax
→ 执行 `python main.py full-sync --provider minimax`
```

- [ ] **Step 3: 创建封装脚本**

```python
#!/usr/bin/env python
# ~/.claude/skills/davybase/scripts/davybase.py
import subprocess
import sys
import os

PROJECT_ROOT = "/Users/qiming/workspace/davybase"
os.chdir(PROJECT_ROOT)

if len(sys.argv) < 2:
    print("用法：davybase <command> [args]")
    sys.exit(1)

command = sys.argv[1]
args = sys.argv[2:]

subprocess.run([sys.executable, "main.py", command] + args)
```

- [ ] **Step 4: 测试 Skill 调用**

```bash
chmod +x ~/.claude/skills/davybase/scripts/davybase.py
~/.claude/skills/davybase/scripts/davybase.py status
```

- [ ] **Step 5: 提交**

注意：Skill 文件在 `~/.claude/skills/` 目录下，不纳入 davybase 仓库。

```bash
# 仅提交项目内文件
git status
```

---

## 执行选择

计划完成并保存到 `docs/superpowers/plans/2026-04-12-knowledge-wiki-pipeline.md`。两个执行选项：

**1. 子代理驱动（推荐）** - 每个任务分派新鲜子代理，任务间审查，快速迭代

**2. 会话内执行** - 使用 executing-plans 在本会话中按任务执行，批量执行带检查点

选择哪种方式？

计划完成并保存到 `docs/superpowers/plans/2026-04-12-knowledge-wiki-pipeline.md`。两个执行选项：

**1. 子代理驱动（推荐）** - 每个任务分派新鲜子代理，任务间审查，快速迭代

**2. 会话内执行** - 使用 executing-plans 在本会话中按任务执行，批量执行带检查点

选择哪种方式？
