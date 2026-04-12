# Task 2: 使用 note-summarizer 生成标题和分类实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 9000+ 条散落笔记生成标题和分类建议

**Architecture:** 
- 使用 note-summarizer Skill 的批量处理能力
- 分两阶段：先生成标题，再分类
- 支持断点续传和进度跟踪

**Tech Stack:** Python, MiniMax LLM, get 笔记 API

**前置条件:** 
- Task 1 已完成：所有散落笔记已抽取到 raw/_inbox 目录
- note-summarizer Skill 已配置并可用

---

## 文件结构

**修改/创建的文件：**
- `~/.claude/skills/note-summarizer/main.py` - 主程序（已有）
- `~/.claude/skills/note-summarizer/scripts/batch_processor.py` - 批量处理脚本（新建）
- `results/summaries.json` - 标题生成结果
- `results/classifications.json` - 分类结果
- `results/progress.json` - 处理进度跟踪

---

## Task 2.1: 确认 note-summarizer Skill 已配置

**Files:**
- Use: `~/.claude/skills/note-summarizer/`

- [ ] **Step 1: 检查 Skill 配置**

```bash
cd ~/.claude/skills/note-summarizer
cat .env 2>/dev/null || echo "无.env 文件"

# 检查环境变量
echo "GETNOTE_API_KEY: ${GETNOTE_API_KEY:-(未设置)}"
echo "MINIMAX_API_KEY: ${MINIMAX_API_KEY:-(未设置)}"
```

- [ ] **Step 2: 验证 Skill 可运行**

```bash
cd ~/.claude/skills/note-summarizer
python main.py --help

# 预期输出：显示可用命令
```

---

## Task 2.2: 创建批量处理脚本

**Files:**
- Create: `~/.claude/skills/note-summarizer/scripts/batch_processor.py`

- [ ] **Step 1: 创建批量处理脚本**

```python
#!/usr/bin/env python3
"""
批量处理散落笔记 - 生成标题和分类
支持断点续传和进度跟踪
"""
import asyncio
import json
import logging
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config_loader import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("note_summarizer.batch")


class BatchProcessor:
    """批量处理器"""
    
    def __init__(self):
        self.config = load_config()
        self.inbox_dir = Path(self.config['inbox_path'])
        self.results_dir = Path(self.config['results_path'])
        self.summaries_file = self.results_dir / "summaries.json"
        self.classifications_file = self.results_dir / "classifications.json"
        self.progress_file = self.results_dir / "batch_progress.json"
        
    def load_progress(self) -> dict:
        """加载进度"""
        if self.progress_file.exists():
            return json.loads(self.progress_file.read_text(encoding='utf-8'))
        return {
            "summarized_ids": [],
            "classified_ids": [],
            "started_at": datetime.now().isoformat()
        }
    
    def save_progress(self, progress: dict):
        """保存进度"""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def load_inbox_notes(self) -> list:
        """加载 inbox 中的所有笔记"""
        notes = []
        for md_file in self.inbox_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                note_id = None
                for line in content.split('\n')[:10]:
                    if line.startswith('note_id:'):
                        note_id = line.split(':')[1].strip()
                        break
                if note_id:
                    notes.append({
                        "note_id": note_id,
                        "file": str(md_file),
                        "content": content
                    })
            except Exception as e:
                logger.error(f"读取笔记失败 {md_file}: {e}")
        return notes
    
    async def run_summarize(self, limit: int = None, resume: bool = True):
        """批量生成标题"""
        progress = self.load_progress()
        summarized_ids = set(progress.get("summarized_ids", []))
        
        notes = self.load_inbox_notes()
        logger.info(f"Inbox 笔记总数：{len(notes)}")
        
        # 过滤已处理的
        pending = [n for n in notes if n["note_id"] not in summarized_ids]
        
        if limit:
            pending = pending[:limit]
            logger.info(f"限制模式：处理前 {limit} 条")
        
        if not resume:
            pending = notes[:limit] if limit else notes
            summarized_ids = set()
            logger.info("重新处理模式")
        
        logger.info(f"待处理：{len(pending)} 条")
        
        if not pending:
            logger.info("没有待处理的笔记")
            return
        
        # 批量处理
        batch_size = 20
        summaries = self._load_existing_summaries()
        
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(pending) + batch_size - 1) // batch_size
            
            logger.info(f"\n批次 {batch_num}/{total_batches} (本批 {len(batch)} 条)")
            
            for note in batch:
                await self._summarize_note(note, summaries)
                summarized_ids.add(note["note_id"])
                
                if len(summarized_ids) % 10 == 0:
                    progress["summarized_ids"] = list(summarized_ids)
                    self.save_progress(progress)
                    logger.info(f"进度：{len(summarized_ids)}/{len(pending)}")
                
                await asyncio.sleep(1.0)
            
            await asyncio.sleep(3.0)
        
        progress["summarized_ids"] = list(summarized_ids)
        self.save_progress(progress)
        logger.info(f"\n✅ 标题生成完成，共 {len(summarized_ids)} 条")
    
    async def _summarize_note(self, note: dict, summaries: list):
        """生成单条笔记标题"""
        # TODO: 调用 note-summarizer 的摘要生成逻辑
        pass
    
    def _load_existing_summaries(self) -> list:
        """加载已有的摘要结果"""
        if self.summaries_file.exists():
            return json.loads(self.summaries_file.read_text(encoding='utf-8'))
        return []
    
    async def run_classify(self, limit: int = None, resume: bool = True):
        """批量分类"""
        progress = self.load_progress()
        classified_ids = set(progress.get("classified_ids", []))
        
        # 加载已生成的摘要
        summaries = self._load_existing_summaries()
        logger.info(f"已有摘要：{len(summaries)} 条")
        
        # 过滤已处理的
        pending = [s for s in summaries if s["note_id"] not in classified_ids]
        
        if limit:
            pending = pending[:limit]
        
        if not resume:
            pending = summaries[:limit] if limit else summaries
            classified_ids = set()
        
        logger.info(f"待分类：{len(pending)} 条")
        
        if not pending:
            logger.info("没有待分类的笔记")
            return
        
        # 批量处理
        batch_size = 20
        classifications = self._load_existing_classifications()
        
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(pending) + batch_size - 1) // batch_size
            
            logger.info(f"\n批次 {batch_num}/{total_batches}")
            
            for summary in batch:
                await self._classify_note(summary, classifications)
                classified_ids.add(summary["note_id"])
                
                if len(classified_ids) % 10 == 0:
                    progress["classified_ids"] = list(classified_ids)
                    self.save_progress(progress)
                
                await asyncio.sleep(1.0)
            
            await asyncio.sleep(3.0)
        
        progress["classified_ids"] = list(classified_ids)
        self.save_progress(progress)
        logger.info(f"\n✅ 分类完成，共 {len(classified_ids)} 条")
    
    async def _classify_note(self, summary: dict, classifications: list):
        """分类单条笔记"""
        # TODO: 调用 note-summarizer 的分类逻辑
        pass
    
    def _load_existing_classifications(self) -> list:
        """加载已有的分类结果"""
        if self.classifications_file.exists():
            return json.loads(self.classifications_file.read_text(encoding='utf-8'))
        return []


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量处理散落笔记")
    parser.add_argument("command", choices=["summarize", "classify", "both"], 
                        help="命令：summarize(生成标题) | classify(分类) | both(两者)")
    parser.add_argument("--limit", type=int, help="限制处理数量（测试用）")
    parser.add_argument("--no-resume", action="store_true", help="不使用断点续传")
    args = parser.parse_args()
    
    processor = BatchProcessor()
    
    if args.command in ["summarize", "both"]:
        await processor.run_summarize(limit=args.limit, resume=not args.no_resume)
    
    if args.command in ["classify", "both"]:
        await processor.run_classify(limit=args.limit, resume=not args.no_resume)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 提交 Skill 更改**

```bash
cd ~/.claude/skills/note-summarizer
git add scripts/batch_processor.py
git commit -m "feat: 批量处理脚本，支持断点续传"
```

---

## Task 2.3: 预览标题生成（5 条样本）

**Files:**
- Use: `~/.claude/skills/note-summarizer/`

- [ ] **Step 1: 运行预览模式**

```bash
cd ~/.claude/skills/note-summarizer

# 预览模式，处理 5 条样本
python scripts/batch_processor.py summarize --limit 5 --no-resume
```

- [ ] **Step 2: 查看预览结果**

```bash
cat results/summaries.json | python -m json.tool | head -50
```

---

## Task 2.4: 批量生成标题（全量 9000+ 条）

**Files:**
- Use: `~/.claude/skills/note-summarizer/`

- [ ] **Step 1: 运行全量标题生成**

```bash
cd ~/.claude/skills/note-summarizer

# 批处理大小 20，自动从中断处恢复
python scripts/batch_processor.py summarize --resume

# 预计耗时：9000 条 / 20 批 * 约 30 秒/批 ≈ 2-3 小时
```

- [ ] **Step 2: 监控进度**

```bash
# 查看进度文件
cat results/batch_progress.json | python -m json.tool

# 或实时查看
watch -n 5 'tail -20 logs/batch.log'
```

- [ ] **Step 3: 验证标题生成结果**

```bash
python -c "
import json
data = json.load(open('results/summaries.json'))
print(f'已生成标题：{len(data)} 条')
print('示例:')
for item in data[:3]:
    print(f\"  - {item.get('note_id')}: {item.get('generated_title')}\")
"
```

---

## Task 2.5: 预览分类结果（5 条样本）

- [ ] **Step 1: 运行预览分类**

```bash
cd ~/.claude/skills/note-summarizer
python scripts/batch_processor.py classify --limit 5 --no-resume
```

- [ ] **Step 2: 查看分类结果**

```bash
cat results/classifications.json | python -m json.tool | head -50
```

---

## Task 2.6: 批量分类（全量 9000+ 条）

- [ ] **Step 1: 运行全量分类**

```bash
python scripts/batch_processor.py classify --resume

# 预计耗时：约 2-3 小时
```

- [ ] **Step 2: 验证分类结果**

```bash
python -c "
import json
from collections import Counter
data = json.load(open('results/classifications.json'))
print(f'已分类：{len(data)} 条')

kb_counts = Counter(item.get('recommended_kb', '未知') for item in data)
print('\n分类分布 Top 10:')
for kb, count in kb_counts.most_common(10):
    print(f'  {kb}: {count} 条')
"
```

---

## 预计耗时

| 阶段 | 预计耗时 |
|------|----------|
| 标题生成 | 2-3 小时 |
| 分类 | 2-3 小时 |
| **总计** | **4-6 小时** |

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| API 限流 | 批次间隔控制，每批后延时 3 秒 |
| LLM 配额不足 | 支持智谱/MiniMax 切换 |
| 中断 | 进度文件支持断点续传 |
| 分类不准确 | 支持人工审核后再执行 |
