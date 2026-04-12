# 散落笔记批量处理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 get 笔记中 9000+ 条散落笔记分批抽取、整理、重命名和分类到知识库

**Architecture:** 
- 第一阶段：使用 Davybase Extractor 全量抽取散落笔记到 raw/_inbox
- 第二阶段：使用 note-summarizer Skill 为每条笔记生成标题和分类建议
- 第三阶段：批量创建知识库并分配笔记

**Tech Stack:** Python, get 笔记 API, note-summarizer Skill, MiniMax LLM

**当前状态：**
- 全部笔记总数：9654 条
- 已同步笔记数：621 条
- **散落笔记（待处理）：9033 条**

---

## 文件结构

**修改/创建的文件：**
- `scripts/batch_extract_inbox.py` - 批量抽取散落笔记脚本
- `scripts/apply_summarizer_results.py` - 执行 note-summarizer 结果脚本
- `results/summaries.json` - 标题生成结果
- `results/classifications.json` - 分类结果
- `results/progress.json` - 处理进度跟踪

---

## Task 1: 全量抽取散落笔记

**Files:**
- Create: `scripts/batch_extract_inbox.py`
- Modify: `src/extractor.py` (可选，增强散落笔记抽取日志)
- Test: 运行脚本验证抽取结果

- [ ] **Step 1: 创建批量抽取脚本**

```python
#!/usr/bin/env python3
"""
批量抽取散落笔记到 raw/_inbox 目录
支持断点续传和进度跟踪
"""
import asyncio
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.extractor import Extractor, GetNoteClient
from src.sync_state import SyncState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("davybase.batch_extract")


class BatchInboxExtractor:
    """散落笔记批量抽取器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.data_path)
        self.inbox_dir = self.data_dir / "_inbox"
        self.progress_file = self.data_dir / ".inbox_extract_progress.json"
        self.state = SyncState(f"{self.data_dir}/sync.db")
        
    def load_progress(self) -> set:
        """加载已抽取的笔记 ID"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get("extracted_ids", []))
        return set()
    
    def save_progress(self, extracted_ids: set):
        """保存抽取进度"""
        self.progress_file.write_text(
            json.dumps({"extracted_ids": list(extracted_ids)}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
    async def run(self):
        """执行批量抽取"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载进度
        extracted_ids = self.load_progress()
        logger.info(f"已抽取 {len(extracted_ids)} 条笔记")
        
        async with GetNoteClient(
            *self.config.get_getnote_credentials()
        ) as client:
            # 获取所有笔记
            all_notes = await client.list_all_notes()
            logger.info(f"全部笔记：{len(all_notes)} 条")
            
            # 获取已同步的笔记 ID
            synced_ids = self.state.get_all_synced_ids()
            
            # 计算散落笔记（未同步且在 raw 目录中不存在）
            raw_synced = self._get_raw_synced_ids()
            inbox_notes = [
                n for n in all_notes 
                if n["note_id"] not in synced_ids 
                and n["note_id"] not in raw_synced
                and n["note_id"] not in extracted_ids
            ]
            
            logger.info(f"待抽取散落笔记：{len(inbox_notes)} 条")
            
            # 批量抽取
            batch_size = 100
            for i in range(0, len(inbox_notes), batch_size):
                batch = inbox_notes[i:i+batch_size]
                logger.info(f"抽取批次 {i//batch_size + 1}/{(len(inbox_notes)-1)//batch_size + 1}")
                
                for note in batch:
                    await self._extract_note(client, note)
                    extracted_ids.add(note["note_id"])
                    
                    # 每 50 条保存一次进度
                    if len(extracted_ids) % 50 == 0:
                        self.save_progress(extracted_ids)
                        logger.info(f"  进度：{len(extracted_ids)}/{len(inbox_notes)}")
                    
                    await asyncio.sleep(0.5)  # 避免限流
                
                await asyncio.sleep(2.0)  # 批次间隔
        
        # 保存最终进度
        self.save_progress(extracted_ids)
        logger.info(f"抽取完成，共 {len(extracted_ids)} 条笔记")
        
    def _get_raw_synced_ids(self) -> set:
        """获取 raw 目录中已同步的笔记 ID"""
        synced_ids = set()
        for kb_dir in self.data_dir.iterdir():
            if kb_dir.is_dir() and kb_dir.name not in ("_inbox", "_failed"):
                for md_file in kb_dir.glob("*.md"):
                    content = md_file.read_text(encoding='utf-8')
                    for line in content.split('\n'):
                        if line.startswith('note_id:'):
                            synced_ids.add(line.split(':')[1].strip())
        return synced_ids
    
    async def _extract_note(self, client: GetNoteClient, note: dict):
        """抽取单条笔记"""
        note_id = note["note_id"]
        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.3)
            
            # 格式化笔记内容
            content = self._format_note_content(detail)
            filename = self._sanitize_filename(detail.get('title', '无标题'))
            
            note_file = self.inbox_dir / f"{note_id}_{filename}.md"
            note_file.write_text(content, encoding='utf-8')
            
            logger.debug(f"  保存笔记 {note_id}")
            
        except Exception as e:
            logger.error(f"  抽取笔记 {note_id} 失败：{e}")
            self._save_failed_note(note, str(e))
    
    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        title = detail.get('title', '')
        if not title:
            content = detail.get("content", "")
            first_line = content.split('\n')[0].strip()[:50]
            title = first_line if first_line and first_line != '#' else detail.get('note_id', '无标题')
        
        lines = [
            "---",
            f"note_id: {detail.get('note_id', '')}",
            f"note_type: {detail.get('note_type', '')}",
            f"created_at: {detail.get('created_at', '')}",
            f"title: {title}",
            f"tags: {detail.get('tags', [])}",
            "---",
            "",
            f"# {title}",
            "",
            detail.get("content", ""),
        ]
        
        if detail.get("web_page", {}).get("content"):
            lines.extend([
                "",
                "---",
                "## 原文链接",
                "",
                detail["web_page"]["content"],
            ])
        
        return "\n".join(lines)
    
    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()[:100]
    
    def _save_failed_note(self, note: dict, error: str):
        """保存失败的笔记"""
        failed_dir = self.data_dir / "_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_file = failed_dir / f"{note['note_id']}.json"
        failed_file.write_text(json.dumps({
            "note": note,
            "error": error
        }, ensure_ascii=False, indent=2), encoding='utf-8')


async def main():
    config = Config()
    extractor = BatchInboxExtractor(config)
    await extractor.run()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行抽取脚本（预览模式）**

```bash
# 先运行前 10 条测试
python scripts/batch_extract_inbox.py --dry-run --limit 10

# 预期输出：
# - 显示待抽取笔记数量
# - 抽取前 10 条到 raw/_inbox
# - 保存进度到 .inbox_extract_progress.json
```

- [ ] **Step 3: 验证抽取结果**

```bash
# 检查 raw/_inbox 目录
ls -la /Users/qiming/ObsidianWiki/raw/_inbox/ | head -20

# 检查笔记内容格式
head -30 /Users/qiming/ObsidianWiki/raw/_inbox/*.md | head -50
```

- [ ] **Step 4: 执行全量抽取**

```bash
# 全量抽取 9000+ 条笔记（预计耗时约 2-3 小时）
python scripts/batch_extract_inbox.py

# 如果中断，可恢复
python scripts/batch_extract_inbox.py --resume
```

- [ ] **Step 5: 提交**

```bash
git add scripts/batch_extract_inbox.py
git commit -m "feat: 散落笔记批量抽取脚本，支持断点续传"
```

---

## Task 2: 使用 note-summarizer 生成标题和分类

**Files:**
- Use: `~/.claude/skills/note-summarizer/main.py`
- Output: `results/summaries.json`, `results/classifications.json`

- [ ] **Step 1: 确认 note-summarizer Skill 已配置**

```bash
# 检查技能是否可用
cd ~/.claude/skills/note-summarizer
python scripts/config_loader.py

# 预期输出：
# 配置加载结果:
#   GETNOTE_API_KEY: 已设置
#   MINIMAX_API_KEY: 已设置
```

- [ ] **Step 2: 预览标题生成（5 条样本）**

```bash
cd ~/.claude/skills/note-summarizer

# 预览模式，处理 5 条样本
python main.py summarize --dry-run --sample 5

# 查看预览结果
cat results/summaries_preview.json | python -m json.tool | head -50
```

- [ ] **Step 3: 批量生成标题（全量 9000+ 条）**

```bash
# 批处理大小 50，自动从中断处恢复
python main.py summarize --batch-size 50 --resume

# 预计耗时：9000 条 / 50 批 * 约 30 秒/批 ≈ 1.5 小时
# 进度文件：results/summarize_progress.json
```

- [ ] **Step 4: 验证标题生成结果**

```bash
# 检查生成的标题数量
python -c "
import json
data = json.load(open('results/summaries.json'))
print(f'已生成标题：{len(data)} 条')
print('示例:')
for item in data[:3]:
    print(f\"  - {item.get('note_id')}: {item.get('generated_title')}\")
"
```

- [ ] **Step 5: 预览分类结果（5 条样本）**

```bash
# 预览模式，处理 5 条样本
python main.py classify --dry-run --sample 5

# 查看预览结果
cat results/classifications_preview.json | python -m json.tool | head -30
```

- [ ] **Step 6: 批量分类（全量 9000+ 条）**

```bash
# 批处理大小 50，自动从中断处恢复
python main.py classify --batch-size 50 --resume

# 预计耗时：约 1.5-2 小时
# 进度文件：results/classify_progress.json
```

- [ ] **Step 7: 验证分类结果**

```bash
# 检查分类结果
python -c "
import json
data = json.load(open('results/classifications.json'))
print(f'已分类：{len(data)} 条')

# 统计分类分布
from collections import Counter
kb_counts = Counter(item.get('recommended_kb', '未知') for item in data)
print('\n分类分布:')
for kb, count in kb_counts.most_common(10):
    print(f'  {kb}: {count} 条')
"
```

---

## Task 3: 执行分类 - 创建知识库并分配笔记

**Files:**
- Use: `~/.claude/skills/note-summarizer/scripts/kb_manager.py`
- Use: `~/.claude/skills/note-summarizer/main.py` (apply 命令)

- [ ] **Step 1: 预览分类执行计划**

```bash
cd ~/.claude/skills/note-summarizer

# 查看将创建的知识库列表
python -c "
import json
data = json.load(open('results/classifications.json'))

from collections import Counter
new_kb_candidates = [
    item for item in data 
    if item.get('action') == 'create_new'
]
kb_names = Counter(item.get('recommended_kb') for item in new_kb_candidates)

print('拟创建的新知识库:')
for name, count in kb_names.most_common(20):
    print(f'  {name}: {count} 条笔记')
"
```

- [ ] **Step 2: 交互式确认（预览模式）**

```bash
# 进入交互式确认
python main.py apply

# 流程：
# 1. 显示分类预览（前 5 条）
# 2. 列出将要创建的新知识库
# 3. 询问是否继续
# 4. 确认后批量执行
```

- [ ] **Step 3: 执行批量分类（创建知识库并分配笔记）**

```bash
# 自动创建模式（无需逐个确认）
python main.py apply --auto-create --batch-size 100

# 预计耗时：约 1-2 小时（创建知识库 + 分配笔记）
```

- [ ] **Step 4: 验证执行结果**

```bash
# 检查 get 笔记 APP 中的知识库
/getnote kb list

# 或运行
cd ~/.claude/skills/note-summarizer
python scripts/kb_manager.py --list
```

---

## Task 4: 使用 Davybase 编译同步到 Obsidian

**Files:**
- Use: `davybase/main.py`
- Output: `/Users/qiming/ObsidianWiki/wiki/`

- [ ] **Step 1: 确认 raw/_inbox 目录已包含所有抽取的笔记**

```bash
cd /Users/qiming/workspace/davybase

# 检查散落笔记数量
ls -1 /Users/qiming/ObsidianWiki/raw/_inbox/*.md | wc -l

# 预期：约 9000 条
```

- [ ] **Step 2: 运行 Davybase 全量同步**

```bash
# 使用智谱 GLM5 编译
python main.py full-sync --provider zhipu

# 或使用 MiniMax
python main.py full-sync --provider minimax

# 预计耗时：9000 条笔记，约 3-4 小时
```

- [ ] **Step 3: 监控同步进度**

```bash
# 查看日志
tail -f logs/sync.log

# 查看同步状态
python main.py status
```

- [ ] **Step 4: 验证 Obsidian Wiki 输出**

```bash
# 检查 wiki 目录
ls -la /Users/qiming/ObsidianWiki/wiki/ | head -20

# 检查生成的 wiki 条目格式
head -50 /Users/qiming/ObsidianWiki/wiki/*.md | head -100
```

---

## Task 5: 清理和总结

- [ ] **Step 1: 清理临时文件**

```bash
# 保留重要的进度文件
# 删除临时缓存（可选）
rm -f /Users/qiming/ObsidianWiki/raw/.inbox_extract_progress.json
```

- [ ] **Step 2: 生成处理报告**

```bash
python -c "
import json
from pathlib import Path
from datetime import datetime

# 读取结果
summaries = json.load(open('results/summaries.json'))
classifications = json.load(open('results/classifications.json'))

print('=' * 60)
print('散落笔记批量处理报告')
print('=' * 60)
print(f'报告时间：{datetime.now().isoformat()}')
print()
print(f'处理笔记总数：{len(summaries)} 条')
print(f'已生成标题：{len(summaries)} 条')
print(f'已分类：{len(classifications)} 条')
print()

# 分类统计
from collections import Counter
kb_dist = Counter(c.get('recommended_kb') for c in classifications)
print('知识库分布 Top 10:')
for kb, count in kb_dist.most_common(10):
    pct = count / len(classifications) * 100
    print(f'  {kb}: {count} 条 ({pct:.1f}%)')
"
```

- [ ] **Step 3: 提交所有更改**

```bash
cd /Users/qiming/workspace/davybase

git add -A
git commit -m "feat: 批量处理 9000+ 条散落笔记

- 新增批量抽取脚本，支持断点续传
- 使用 note-summarizer 生成标题和分类
- 自动创建知识库并分配笔记
- 同步到 Obsidian Wiki

处理统计：
- 抽取散落笔记：9033 条
- 生成标题：9033 条
- 分类笔记：9033 条
- 创建/更新知识库：XX 个
"

git push
```

---

## 预计总耗时

| 阶段 | 预计耗时 | 说明 |
|------|----------|------|
| Task 1: 抽取 | 2-3 小时 | 9000+ 条，受 API 限流影响 |
| Task 2: 标题 + 分类 | 3-4 小时 | LLM 调用，MiniMax 处理 |
| Task 3: 执行分类 | 1-2 小时 | 创建知识库 + 分配 |
| Task 4: Davybase 同步 | 3-4 小时 | LLM 编译 + Obsidian 写入 |
| **总计** | **9-13 小时** | 可中断恢复，建议分天执行 |

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| API 限流 | 内置指数退避，批次间隔控制 |
| LLM 配额不足 | 支持智谱/MiniMax 切换 |
| 中断 | 所有阶段支持断点续传 |
| 分类不准确 | 支持人工审核后再执行 |

---

## 执行选择

**推荐：分阶段执行**

1. **Day 1**: Task 1 - 抽取散落笔记
2. **Day 2**: Task 2 - 生成标题和分类
3. **Day 3**: Task 3 + Task 4 - 执行分类并同步到 Obsidian
4. **Day 4**: Task 5 - 清理和总结

**Which approach?**
1. Subagent-Driven - 分派子代理逐个任务执行，自动审查
2. Manual Step-by-Step - 手动逐步执行，每步确认
