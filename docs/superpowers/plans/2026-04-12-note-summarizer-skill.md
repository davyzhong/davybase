# 笔记摘要与自动分类 Skill 创建计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 创建一个独立的 Claude Code Skill，用于自动分析 get 笔记中的散落笔记，生成标题并推荐知识库分类

**Architecture:** 基于测试结果（3/5 成功，标题生成和分类准确率 100%），将 Python 测试脚本重构为可复用的 Skill，支持批处理和交互式确认

**Tech Stack:** 
- Python 异步脚本（httpx + asyncio）
- MiniMax LLM API（codex-MiniMax-M2.7 模型）
- get 笔记 OpenAPI
- JSON 结构化输出解析

### 分类策略（重要更新）

分类逻辑分为三个层级：

1. **匹配现有知识库** - 如果内容与现有知识库高度匹配（置信度 high），直接推荐
2. **建议新知识库** - 如果内容无法匹配现有知识库，LLM 生成新知识库名称
3. **批量智能分组** - 处理大量笔记时，自动聚类形成知识库分组建议

**分类输出格式：**
```json
{
    "recommended_kb": "经营&管理",  // 现有知识库名称
    "action": "use_existing",       // 使用现有知识库
    "confidence": "high",
    "reason": "..."
}
```
或
```json
{
    "recommended_kb": "AI 与软件工程",  // 新知识库名称
    "action": "create_new",           // 创建新知识库
    "confidence": "medium",
    "reason": "内容聚焦 AI 编程范式，现有知识库无匹配主题",
    "similar_notes_count": 15  // 预估有相似主题的笔记数量
}
```

---

## Task 1: Skill 基础结构

**Files:**
- Create: `~/.claude/skills/note-summarizer/_meta.json`
- Create: `~/.claude/skills/note-summarizer/SKILL.md`
- Create: `~/.claude/skills/note-summarizer/README.md`
- Create: `~/.claude/skills/note-summarizer/package.json`
- Create: `~/.claude/skills/note-summarizer/scripts/summarize.py`

- [ ] **Step 1: 创建 Skill 目录结构**

```bash
mkdir -p ~/.claude/skills/note-summarizer/{scripts,references}
```

- [ ] **Step 2: 创建 _meta.json**

```json
{
  "ownerId": "kn75rbp8nyw5q0xmrzg01nfeq5829kd0",
  "slug": "note-summarizer",
  "version": "1.0.0",
  "publishedAt": 1776000000000
}
```

- [ ] **Step 3: 创建 SKILL.md（指令定义）**

参考 getnote skill 格式，定义：
- 触发指令：`/note summarize`、`/note auto-classify`
- 自然语言路由：「总结笔记」「生成标题」「自动分类」
- 配置要求：GETNOTE_API_KEY, MINIMAX_API_KEY

- [ ] **Step 4: 创建 package.json**

```json
{
  "name": "note-summarizer",
  "version": "1.0.0",
  "description": "Get 笔记智能摘要与自动分类",
  "scripts": {
    "summarize": "python scripts/summarize.py"
  }
}
```

---

## Task 2: 核心功能实现

**Files:**
- Create: `~/.claude/skills/note-summarizer/scripts/summarize.py`
- Create: `~/.claude/skills/note-summarizer/scripts/classify.py`

- [ ] **Step 1: 实现 `summarize.py`（标题生成）**

```python
#!/usr/bin/env python3
"""为散落笔记生成标题"""

import asyncio
import json
from pathlib import Path
import httpx

# 配置
GETNOTE_API_KEY = os.getenv("GETNOTE_API_KEY")
GETNOTE_CLIENT_ID = os.getenv("GETNOTE_CLIENT_ID", "cli_a1b2c3d4e5f6789012345678abcdef90")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
MINIMAX_URL = "https://api.minimaxi.com/v1/chat/completions"
MINIMAX_MODEL = "codex-MiniMax-M2.7"

PROMPT_TEMPLATE = """请为以下笔记内容生成一个简洁明确的标题（10-30 字）：

笔记内容：
{content}

请只输出标题，不要有其他内容。"""

async def generate_title(content: str) -> str:
    """调用 MiniMax 生成标题"""
    # 实现 HTTP 请求逻辑
    pass

async def main():
    # 获取散落笔记列表
    # 逐条生成标题
    # 输出结果
    pass
```

- [ ] **Step 2: 实现 `classify.py`（知识库分类，支持新知识库）**

```python
PROMPT_TEMPLATE = """请分析以下笔记内容，完成分类任务：

**现有知识库列表**：{kb_list}

**笔记内容**：
{content}

**分类规则**：
1. 如果内容与现有知识库高度匹配，推荐现有知识库
2. 如果内容无法匹配现有知识库，建议一个新的知识库名称
3. 输出 JSON 格式

请按 JSON 格式输出：
```json
{
    "recommended_kb": "知识库名称",
    "action": "use_existing" 或 "create_new",
    "confidence": "high/medium/low",
    "reason": "分类理由，如果建议新建需说明原因"
}
```
只输出 JSON，不要有其他内容。"""
```
```

- [ ] **Step 3: 实现配置加载工具函数**

```python
def load_config():
    """从~/.openclaw/openclaw.json 和~/.zshrc 加载 API 密钥"""
    pass
```

---

## Task 3: 批处理与进度管理

**Files:**
- Create: `~/.claude/skills/note-summarizer/scripts/batch_processor.py`

- [ ] **Step 1: 实现分批处理逻辑**

```python
async def process_batch(notes: list, batch_size: int = 20):
    """分批处理笔记，避免限流"""
    for i in range(0, len(notes), batch_size):
        batch = notes[i:i+batch_size]
        await process_single_batch(batch)
        # 避免限流
        await asyncio.sleep(5.0)
```

- [ ] **Step 2: 实现进度持久化**

```python
def save_progress(processed_ids: set, output_file: str):
    """保存处理进度，支持中断恢复"""
    pass

def load_progress(output_file: str) -> set:
    """加载已处理的笔记 ID"""
    pass
```

- [ ] **Step 3: 实现进度报告**

```python
def print_progress(current: int, total: int, success: int, failed: int):
    """打印处理进度"""
    percentage = (current / total) * 100
    print(f"进度：{current}/{total} ({percentage:.1f}%), 成功：{success}, 失败：{failed}")
```

---

## Task 4: 交互式确认功能

**Files:**
- Modify: `~/.claude/skills/note-summarizer/scripts/summarize.py`
- Create: `~/.claude/skills/note-summarizer/scripts/interactive.py`

- [ ] **Step 1: 实现 dry-run 模式**

```python
async def dry_run(sample_size: int = 10):
    """预览模式：处理少量样本，让用户确认效果"""
    # 获取 sample_size 条笔记
    # 生成标题和分类
    # 打印预览结果（区分现有知识库和新建议知识库）
    # 询问用户是否继续
```

- [ ] **Step 2: 实现交互式确认（支持新知识库创建）**

```python
def confirm_action(results: list) -> dict:
    """
    展示结果并询问用户是否继续
    
    返回：
    {
        "approved": True,
        "create_new_kbs": ["AI 与软件工程", "财务管理"],  # 用户批准创建的新知识库
        "skip_categories": ["low"]  # 跳过低置信度分类
    }
    """
    print("=== 预览结果 ===")
    
    # 分组展示
    use_existing = [r for r in results if r.get("action") == "use_existing"]
    create_new = [r for r in results if r.get("action") == "create_new"]
    
    print(f"\n使用现有知识库 ({len(use_existing)} 条):")
    for r in use_existing:
        print(f"  - {r['note_id']}: {r['title']} → {r['recommended_kb']} ({r['confidence']})")
    
    print(f"\n建议新知识库 ({len(create_new)} 条):")
    for r in create_new:
        print(f"  - {r['note_id']}: {r['title']} → [新] {r['recommended_kb']} ({r['confidence']})")
        print(f"    理由：{r['reason']}")
    
    # 交互式确认
    print("\n操作选项:")
    print("  1. 全部批准 (a)")
    print("  2. 仅批准使用现有知识库 (e)")
    print("  3. 仅批准新知识库 (n)")
    print("  4. 自定义批准 (c)")
    print("  5. 取消 (q)")
    
    response = input("请选择 (a/e/n/c/q): ")
    # ...处理选择
```

- [ ] **Step 3: 实现批量聚类分析（可选高级功能）**

```python
async def cluster_notes(notes: list, k: int = None) -> list:
    """
    基于内容相似度自动聚类笔记
    
    如果 k=None，自动确定最佳聚类数量
    返回聚类结果，每组包含相似的笔记 ID 列表和主题摘要
    """
    # 使用 LLM 分析笔记主题
    # 或使用向量相似度聚类
    pass
```

- [ ] **Step 4: 添加命令行参数**

```python
import argparse

parser = argparse.ArgumentParser(description='笔记摘要与自动分类工具')
parser.add_argument('--dry-run', action='store_true', help='预览模式')
parser.add_argument('--sample', type=int, default=5, help='预览样本数量')
parser.add_argument('--batch-size', type=int, default=20, help='每批处理数量')
parser.add_argument('--resume', action='store_true', help='从中断处恢复')
parser.add_argument('--auto-create', action='store_true', help='自动创建新知识库（无需确认）')
parser.add_argument('--cluster', action='store_true', help='启用聚类分析')
```

---

## Task 5: 错误处理与日志

**Files:**
- Create: `~/.claude/skills/note-summarizer/scripts/logger.py`

- [ ] **Step 1: 实现日志记录**

```python
import logging

logger = logging.getLogger("note-summarizer")

def setup_logger(log_file: str = "summarize.log"):
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
```

- [ ] **Step 2: 实现错误重试机制**

```python
async def call_llm_with_retry(func, max_retries: int = 3):
    """LLM 调用失败时自动重试"""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = min(60, 10 * (2 ** attempt))
                logger.warning(f"失败，等待{wait_time}秒后重试...")
                await asyncio.sleep(wait_time)
            else:
                raise
```

- [ ] **Step 3: 生成处理报告**

```python
def generate_report(results: list, output_file: str):
    """生成处理报告"""
    report = {
        "total": len(results),
        "success": len([r for r in results if r.get("success")]),
        "failed": len([r for r in results if not r.get("success")]),
        "details": results
    }
    with open(output_file, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
```

---

## Task 5.5: 知识库创建 API 集成（新增）

**Files:**
- Create: `~/.claude/skills/note-summarizer/scripts/kb_manager.py`

- [ ] **Step 1: 实现知识库创建函数**

```python
async def create_knowledge_base(name: str, description: str = "") -> dict:
    """
    调用 get 笔记 API 创建新知识库
    
    API: POST /open/api/v1/resource/knowledge/create
    """
    async with httpx.AsyncClient(...) as client:
        resp = await client.post(
            f"{BASE_URL}/open/api/v1/resource/knowledge/create",
            json={
                "name": name,
                "description": description,
                "type": "user_created"
            }
        )
        result = resp.json()
        if result.get("success"):
            return result.get("data", {})
        else:
            raise Exception(f"创建知识库失败：{result.get('error', {}).get('message')}")
```

- [ ] **Step 2: 实现笔记添加到知识库**

```python
async def add_notes_to_kb(topic_id: str, note_ids: list) -> bool:
    """
    将笔记批量添加到知识库
    
    API: POST /open/api/v1/resource/knowledge/note/batch-add
    """
    async with httpx.AsyncClient(...) as client:
        resp = await client.post(
            f"{BASE_URL}/open/api/v1/resource/knowledge/note/batch-add",
            json={
                "topic_id": topic_id,
                "note_ids": note_ids
            }
        )
        result = resp.json()
        return result.get("success", False)
```

- [ ] **Step 3: 实现知识库名称冲突检测**

```python
async def check_kb_exists(name: str, existing_kbs: list) -> tuple[bool, str]:
    """
    检查知识库名称是否已存在
    
    返回：(是否存在，如果存在返回 topic_id)
    """
    for kb in existing_kbs:
        if kb["name"] == name:
            return True, kb["topic_id"]
    return False, None
```

---

## Task 6: 命令行入口集成

**Files:**
- Create: `~/.claude/skills/note-summarizer/main.py`

- [ ] **Step 1: 创建 CLI 入口**

```python
#!/usr/bin/env python3
"""笔记摘要与自动分类工具 - CLI 入口"""

import asyncio
import argparse
from scripts.summarize import run_summarize
from scripts.classify import run_classify
from scripts.kb_manager import execute_classification

def main():
    parser = argparse.ArgumentParser(description='笔记摘要与自动分类工具')
    parser.add_argument("command", choices=["summarize", "classify", "apply", "both"],
                        help="命令：summarize(生成标题), classify(分类), apply(执行分类创建知识库), both(两者)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--sample", type=int, default=5, help="预览样本数量")
    parser.add_argument("--batch-size", type=int, default=20, help="每批处理数量")
    parser.add_argument("--resume", action="store_true", help="从中断处恢复")
    parser.add_argument("--auto-create", action="store_true", help="自动创建新知识库（无需确认）")
    parser.add_argument("--cluster", action="store_true", help="启用聚类分析")
    
    args = parser.parse_args()
    
    if args.command == "summarize":
        asyncio.run(run_summarize(args))
    elif args.command == "classify":
        asyncio.run(run_classify(args))
    elif args.command == "apply":
        # 执行分类：创建新知识库并将笔记添加进去
        asyncio.run(execute_classification(args))
    elif args.command == "both":
        asyncio.run(run_summarize(args))
        asyncio.run(run_classify(args))
```

- [ ] **Step 2: 测试命令行**

```bash
# 预览模式（5 条样本）
python main.py summarize --dry-run --sample 5

# 批量处理（每批 50 条）
python main.py summarize --batch-size 50

# 执行分类（自动创建新知识库）
python main.py apply --auto-create

# 交互式执行分类
python main.py classify --dry-run
```

---

## Task 7: 文档与使用说明

**Files:**
- Create: `~/.claude/skills/note-summarizer/USAGE.md`

- [ ] **Step 1: 编写使用文档**

```markdown
# 笔记摘要与自动分类 - 使用说明

## 快速开始

### 1. 配置要求
- `GETNOTE_API_KEY`: Get 笔记 API 密钥
- `GETNOTE_CLIENT_ID`: Get 笔记 Client ID
- `MINIMAX_API_KEY`: MiniMax LLM API 密钥

### 2. 预览效果
```bash
python main.py summarize --dry-run --sample 5
```

### 3. 批量处理
```bash
python main.py summarize --batch-size 50
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `summarize` | 为散落笔记生成标题 |
| `classify` | 为散落笔记推荐知识库分类 |
| `both` | 同时执行摘要和分类 |

## 输出文件

- `results/summaries.json`: 标题生成结果
- `results/classifications.json`: 分类结果
- `logs/summarize.log`: 处理日志
```

- [ ] **Step 2: 更新 SKILL.md 的自然语言路由**

添加：
```
「总结笔记」「生成标题」「自动分类」→ /note summarize
```

---

## Task 8: 测试与验证

**Files:**
- Create: `~/.claude/skills/note-summarizer/tests/test_summarize.py`

- [ ] **Step 1: 单元测试**

```python
async def test_generate_title():
    """测试标题生成"""
    content = "这是一段测试内容..."
    title = await generate_title(content)
    assert 10 <= len(title) <= 50
    assert title.strip() != ""
```

- [ ] **Step 2: 集成测试**

```bash
# 使用真实 API 测试
python main.py summarize --dry-run --sample 3
```

- [ ] **Step 3: 验证输出格式**

检查生成的 JSON 结果是否符合预期格式

---

## 验收标准

- [ ] Skill 可以独立运行
- [ ] 预览模式正常工作
- [ ] 批处理支持中断恢复
- [ ] 错误处理完善（限流、超时、API 错误）
- [ ] 文档完整清晰
- [ ] 测试结果符合预期（标题生成准确率 > 80%，分类准确率 > 80%）

---

## 时间估算

| Task | 预计时间 |
|------|---------|
| Task 1: 基础结构 | 15 分钟 |
| Task 2: 核心功能 | 45 分钟 |
| Task 3: 批处理 | 30 分钟 |
| Task 4: 交互确认 | 20 分钟 |
| Task 5: 错误处理 | 25 分钟 |
| Task 6: CLI 集成 | 15 分钟 |
| Task 7: 文档编写 | 20 分钟 |
| Task 8: 测试验证 | 30 分钟 |
| **总计** | **约 3.5 小时** |

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| MiniMax API 不稳定 | 中 | 实现指数退避重试 |
| 处理大量笔记耗时 | 高 | 支持断点续传，分批处理 |
| 分类准确率不足 | 中 | 增加 few-shot examples，优化 prompt |
| 限流问题 | 低 | 控制请求频率，增加延时 |
