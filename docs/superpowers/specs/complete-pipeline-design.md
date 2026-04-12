# Davybase 完整知识生产线设计文档

> 基于参考项目设计理念 + 当前能力缺口分析 + 目录结构重构方案

---

## 一、设计目标

构建一条**全自动、可定时执行、幂等安全**的知识处理生产线，将 get 笔记中的原始内容转化为结构化 Wiki 知识。

### 核心原则

| 原则 | 说明 | 实现方式 |
|------|------|----------|
| **幂等性** | 任何步骤可安全重复执行 | 状态标识 + 进度追踪 |
| **原子化** | 每条笔记单一主题、可独立理解 | Atomic Notes 四条原则 |
| **断点续传** | 中断后从中断处恢复 | JSON 进度文件 + SQLite |
| **无人值守** | 定时任务自动执行 | 预设规则 + 异常降级 |

---

## 二、完整生产线架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Davybase 知识生产线 v2.0                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   摄取阶段              消化阶段                 编译阶段            输出阶段    │
│   (Ingest)             (Digest)                (Compile)           (Publish)   │
│                                                                                 │
│   ┌──────────┐       ┌──────────┐            ┌──────────┐       ┌──────────┐  │
│   │ get 笔记 API│────>│ raw/    │───────────>│ processed│──────>│   wiki/  │  │
│   │ 本地文件  │       │ notes/  │            │   /      │       │          │  │
│   │ PDF/Word │       │         │            │  {KB}/   │       │          │  │
│   └──────────┘       └──────────            └──────────       └──────────┘  │
│        │                    │                      │                   │        │
│        ▼                    ▼                      ▼                   ▼        │
│  ┌──────────┐         ┌──────────          ┌──────────┐        ┌──────────┐   │
│  │ ingest.py│         │ digest.py│          │ compile.py│       │ publish.py│  │
│  │          │         │          │          │          │        │          │   │
│  │ • API 抽取 │         │ • 标题生成 │          │ • 聚合编译 │       │ • HTML 卡片│  │
│  │ • 文件导入 │         │ • 智能分类 │          │ • 双链生成 │       │ • 卡片输出│  │
│  │ • 格式转换 │         │ • 原子拆解 │          │ • 概念提取 │       │ • 发布通知│  │
│  └──────────┘         └──────────          └──────────┘        └──────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、目录结构（最终态）

```
/ObsidianWiki/
│
├── raw/                            # 原始文件库（只读，不直接编辑）
│   ├── notes/                      # get 笔记原始导出
│   │   ├── _inbox/                 # 散落笔记（未分类）
│   │   ├── 知识库 1/               # 按 get 笔记知识库分组
│   │   └── 知识库 2/
│   │
│   ├── documents/                  # 文档类（PDF, Word, PPT 等）
│   │   ├── _inbox/                 # 待处理的文档
│   │   └── processed/              # 已提取文本的文档（标记）
│   │
│   ├── images/                     # 图片类
│   │   └── _inbox/                 # 待 OCR 处理的图片
│   │
│   └── audio/                      # 录音类
│       └── _inbox/                 # 待转写的录音
│
├── processed/                      # ✨ 处理后的干净 Markdown（主要工作区）
│   ├── _inbox/                     # 待处理的散落笔记（已加标题/分类标签）
│   ├── 经营&管理/                  # 已分类的知识库目录
│   ├── 编程+AI/
│   ├── 学习&思考/
│   └── ...
│
├── wiki/                           # LLM 编译后的结构化 Wiki 条目
│   ├── 反向传播算法.md
│   ├── Transformer 模型.md
│   └── ...
│
├── cards/                          # ✨ HTML 知识卡片（可选输出）
│   └── {date}/                     # 按日期分组
│       ├── card_001.html
│       └── ...
│
├── logs/                           # 日志文件
│   ├── ingest_{date}.log
│   ├── digest_{date}.log
│   ├── compile_{date}.log
│   └── publish_{date}.log
│
└── .davybase/                      # ✨ 状态追踪数据
    ├── sync.db                     # SQLite 数据库（同步状态）
    ├── ingest_progress.json        # 摄取进度
    ├── digest_progress.json        # 消化进度
    ├── compile_progress.json       # 编译进度
    └── publish_manifest.json       # 发布清单
```

---

## 四、各阶段详细设计

### 阶段 1: 摄取 (Ingest)

**脚本**: `scripts/ingest.py`

**职责**:
- 从 get 笔记 API 抽取原始笔记
- 从本地导入 PDF/Word/PPT 等文档
- 统一转换为 Markdown 格式（markitdown）
- 存放到 `raw/notes/_inbox/` 或 `raw/documents/_inbox/`

**输入**:
- get 笔记 API
- 本地文件（PDF, Word, PPT, 图片，录音）

**输出**:
- `raw/notes/_inbox/{note_id}_{title}.md`
- `raw/documents/_inbox/{filename}.md`

**幂等性检查**:
```python
if note_id in extracted_ids:
    logger.info(f"跳过已抽取：{note_id}")
    return
```

**配置**:
```yaml
ingest:
  batch_size: 100           # 批量抽取数量
  rate_limit_delay: 2.0     # API 请求间隔（秒）
  max_retries: 3            # 失败重试次数
  providers:
    - getnote               # get 笔记 API
    - local_files           # 本地文件导入
```

---

### 阶段 2: 消化 (Digest)

**脚本**: `scripts/digest.py`

**职责**:
- 为原始笔记生成标题（无标题笔记）
- 智能分类到合适的知识库
- 遵循 Atomic Notes 原则进行拆解
- 输出到 `processed/_inbox/` 或直接到 `processed/{知识库}/`

**输入**:
- `raw/notes/_inbox/*.md`
- `raw/documents/_inbox/*.md`

**输出**:
- `processed/_inbox/{note_id}_{title}.md`（带 Frontmatter）
- 或直接移动到 `processed/{知识库}/{title}.md`

**Frontmatter 格式**:
```yaml
---
note_id: 1871069389378457864
source: raw/notes/_inbox/1871069389378457864_.md
title: 一个人如果不曾全力以赴
generated_title: true
recommended_kb: 学习&思考
classification_confidence: 0.92
summarized: true
summarized_at: '2026-04-13T06:15:20'
classified: true
classified_at: '2026-04-13T06:15:25'
atomic_notes:
  - topic: 全力以赴的重要性
    summary: 一个人如果不曾全力以赴，大概不会知道自己的边界
tags: [成长，自我认知]
---
```

**Atomic Notes 拆解规则**:
```python
# 检查是否需要拆解
def needs_splitting(note: dict) -> bool:
    # 规则 1: 字数超过 2000
    if len(note['content']) > 2000:
        return True
    
    # 规则 2: 包含多个独立主题（LLM 判断）
    topics = llm.extract_topics(note['content'])
    if len(topics) > 1:
        return True
    
    # 规则 3: 包含多个子标题且有独立价值
    if note.get('subsections', []) and len(note['subsections']) > 2:
        return True
    
    return False

# 拆解后输出
def split_note(note: dict) -> list[dict]:
    """拆解一条笔记为多条原子笔记"""
    atomic_notes = llm.split_to_atomic_units(note)
    for atomic in atomic_notes:
        atomic['source_note_id'] = note['note_id']
        atomic['is_atomic'] = True
    return atomic_notes
```

**配置**:
```yaml
digest:
  batch_size: 50            # 批量处理数量
  rate_limit_delay: 1.0     # LLM 请求间隔
  atomic_notes:
    enabled: true           # 启用原子化拆解
    max_length: 2000        # 单条原子笔记最大字数
    min_confidence: 0.7     # 最小分类置信度
  auto_classify:
    enabled: true           # 自动分类
    match_threshold: 0.8    # 匹配现有知识库阈值
    create_new_threshold: 10 # 创建新库最小笔记数
```

---

### 阶段 3: 编译 (Compile)

**脚本**: `src/compiler.py`（重构）

**职责**:
- 读取 `processed/` 中的 Markdown
- 将多条相关笔记聚合为结构化 Wiki 条目
- 自动生成双向链接 `[[概念]]`
- 提取核心概念和关键术语

**输入**:
- `processed/{知识库}/*.md`

**输出**:
- `wiki/{概念名}.md`

**Wiki 条目格式**:
```markdown
---
title: 反向传播算法
source:
  - processed/编程+AI/神经网络基础/reverse_prop.md
  - processed/编程+AI/深度学习/gradient.md
tags: [深度学习，神经网络，算法]
created: 2026-04-13
type: wiki
concepts: [梯度下降，链式法则，自动微分]
---

# 反向传播算法

%%davybase-auto-begin%%
## 核心摘要
反向传播算法是神经网络训练的核心，通过链式法则计算梯度...

## 关键概念
- [[梯度下降]]
- [[链式法则]]
- [[自动微分]]

## 详细解释
反向传播（Backpropagation）是...

## 应用场景
- 神经网络训练
- 深度学习模型优化
%%davybase-auto-end%%

## 相关笔记
- [[Transformer 模型]]
- [[注意力机制]]

## 来源
- [一个人如果不曾全力以赴](processed/学习&思考/全力以赴.md)
- [历史、政治、文学这些东西](processed/学习&思考/晶体智力.md)
```

**双向链接生成**:
```python
def extract_concepts(text: str) -> list[str]:
    """从文本中提取概念，生成双向链接"""
    # 使用 LLM 提取领域概念
    prompt = f"""
    从以下文本中提取专业概念和术语，每个概念 2-8 个字：
    
    {text}
    
    输出格式：JSON 列表，如 ["梯度下降", "链式法则"]
    """
    concepts = llm.complete(prompt)
    return concepts

def add_wikilinks(text: str, concepts: list[str]) -> str:
    """为概念添加 [[wikilink]]"""
    for concept in concepts:
        # 避免重复添加
        if f'[[{concept}]]' not in text:
            text = text.replace(concept, f'[[{concept}]]', 1)
    return text
```

**配置**:
```yaml
compile:
  batch_size: 15            # 单批次最大笔记数
  max_retries: 2            # LLM 调用最大重试次数
  default_provider: zhipu
  wikilinks:
    enabled: true           # 启用双向链接
    min_concept_length: 2   # 概念最小字数
    max_concept_length: 8   # 概念最大字数
  aggregation:
    min_notes: 3            # 最少几条笔记聚合为 Wiki
    topic_similarity: 0.7   # 主题相似度阈值
```

---

### 阶段 4: 输出 (Publish)

**脚本**: `scripts/publish.py`（新建）

**职责**:
- 基于 Wiki 条目生成 HTML 知识卡片
- 支持分享到社交媒体
- 可选：发布到博客/网站

**输入**:
- `wiki/*.md`

**输出**:
- `cards/{date}/{title}.html`

**HTML 卡片模板**:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}} - Davybase 知识卡片</title>
    <style>
        /* 固定样式，不随内容改变 */
        :root {
            --primary-color: #2196F3;
            --bg-color: #f5f5f5;
            --card-bg: #ffffff;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI"; }
        .card { max-width: 600px; margin: 40px auto; padding: 30px; }
        .title { font-size: 24px; color: var(--primary-color); }
        .tags { margin-top: 20px; }
        .tag { display: inline-block; padding: 4px 12px; background: #e3f2fd; border-radius: 16px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h1 class="title">{{title}}</h1>
        <div class="content">
            {{content}}
        </div>
        <div class="tags">
            {% for tag in tags %}
            <span class="tag">{{tag}}</span>
            {% endfor %}
        </div>
        <div class="footer">
            <small>来自 <a href="https://davybase.com">Davybase</a></small>
        </div>
    </div>
</body>
</html>
```

**配置**:
```yaml
publish:
  enabled: true             # 启用发布
  html_cards:
    enabled: true           # 生成 HTML 卡片
    template: cards/default.html
    output_dir: cards/
  social:
    enabled: false          # 社交媒体分享（可扩展）
    platforms: [twitter, weibo]
```

---

## 五、定时任务设计

### 每日自动执行流程

```bash
# crontab 配置（每天凌晨 3 点执行）
0 3 * * * /Users/qiming/workspace/davybase/scripts/daily_pipeline.sh >> /Users/qiming/ObsidianWiki/logs/daily_$(date +\%Y\%m\%d).log 2>&1
```

### 执行脚本 `scripts/daily_pipeline.sh`

```bash
#!/bin/bash

# Davybase 每日知识生产线执行脚本
# 执行顺序：摄取 → 消化 → 编译 → 输出

set -e  # 遇到错误立即退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="/Users/qiming/ObsidianWiki"
DATE=$(date +%Y%m%d)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

cd "$BASE_DIR"

log "========== 开始每日知识生产线 =========="

# 阶段 1: 摄取
log "[1/4] 摄取阶段：从 get 笔记 API 抽取新笔记..."
python scripts/ingest.py --resume --log-file "$DATA_DIR/logs/ingest_$DATE.log"
if [ $? -ne 0 ]; then
    log "❌ 摄取阶段失败，跳过后续阶段"
    exit 1
fi
log "✓ 摄取阶段完成"

# 阶段 2: 消化
log "[2/4] 消化阶段：生成标题和分类..."
python scripts/digest.py --resume --log-file "$DATA_DIR/logs/digest_$DATE.log"
if [ $? -ne 0 ]; then
    log "❌ 消化阶段失败，跳过后续阶段"
    exit 1
fi
log "✓ 消化阶段完成"

# 阶段 3: 编译
log "[3/4] 编译阶段：聚合笔记生成 Wiki..."
python src/compiler.py --provider zhipu --log-file "$DATA_DIR/logs/compile_$DATE.log"
if [ $? -ne 0 ]; then
    log "❌ 编译阶段失败，跳过后续阶段"
    exit 1
fi
log "✓ 编译阶段完成"

# 阶段 4: 输出
log "[4/4] 输出阶段：生成 HTML 知识卡片..."
python scripts/publish.py --log-file "$DATA_DIR/logs/publish_$DATE.log"
log "✓ 输出阶段完成"

log "========== 每日知识生产线完成 =========="

# 发送通知（可扩展）
# python scripts/notify.py --status success --date "$DATE"
```

### 各阶段独立执行命令

```bash
# 单独执行某个阶段
python scripts/ingest.py --resume          # 摄取
python scripts/digest.py --resume          # 消化
python src/compiler.py --provider zhipu    # 编译
python scripts/publish.py                  # 输出

# 预览模式（不实际执行）
python scripts/ingest.py --dry-run --limit 10
python scripts/digest.py --dry-run --limit 5
```

---

## 六、状态追踪与幂等性

### 状态标识体系

```yaml
# Frontmatter 中的状态标识
summarized: true          # 已生成标题
summarized_at: '2026-04-13T06:15:20'
classified: true          # 已分类
classified_at: '2026-04-13T06:15:25'
moved_to_kb: '学习&思考'  # 已移动到知识库
moved_at: '2026-04-13T06:15:30'
compiled: true            # 已编译为 Wiki
compiled_at: '2026-04-13T06:20:00'
published: true           # 已发布
published_at: '2026-04-13T06:25:00'
```

### 进度文件格式

```json
// .davybase/ingress_progress.json
{
  "last_run": "2026-04-13T03:00:00",
  "extracted_ids": ["1871069389378457864", ...],
  "failed_ids": [],
  "status": "completed"
}

// .davybase/digest_progress.json
{
  "last_run": "2026-04-13T03:10:00",
  "notes": {
    "1871069389378457864": {
      "summarized": true,
      "classified": true,
      "recommended_kb": "学习&思考",
      "processed_at": "2026-04-13T03:10:15"
    }
  },
  "status": "completed"
}
```

### 幂等性检查函数

```python
class ProcessingStatus:
    """处理状态管理器"""
    
    def __init__(self, status_file: str):
        self.status_file = Path(status_file)
        self.status = self._load()
    
    def is_ingested(self, note_id: str) -> bool:
        return note_id in self.status.get("extracted_ids", [])
    
    def is_summarized(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("summarized", False)
    
    def is_classified(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("classified", False)
    
    def is_moved(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("moved_to_kb") is not None
    
    def is_compiled(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("compiled", False)
    
    def mark_summarized(self, note_id: str, data: dict):
        self.status.setdefault("notes", {}).setdefault(note_id, {}).update(data)
        self._save()
    
    def _load(self) -> dict:
        if self.status_file.exists():
            return json.loads(self.status_file.read_text(encoding='utf-8'))
        return {}
    
    def _save(self):
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=2), encoding='utf-8')

# 使用方式
async def process_note(note: dict):
    note_id = note['note_id']
    
    if status.is_summarized(note_id):
        logger.info(f"跳过已处理：{note_id}")
        return
    
    # 执行实际处理...
    await summarize(note)
    status.mark_summarized(note_id, {
        "summarized": True,
        "summarized_at": datetime.now().isoformat()
    })
```

---

## 七、错误处理与降级策略

### 错误处理机制

```python
class PipelineError(Exception):
    """管线错误基类"""
    pass

class IngestError(PipelineError):
    """摄取错误"""
    pass

class DigestError(PipelineError):
    """消化错误"""
    pass

# 带降级的执行
async def run_with_fallback(func, fallbacks: list, default=None):
    """带自动降级的执行"""
    last_error = None
    for fallback in fallbacks:
        try:
            return await func(fallback)
        except Exception as e:
            last_error = e
            logger.warning(f"{fallback} 失败：{e}")
            continue
    
    logger.error(f"所有降级方案均失败：{last_error}")
    return default
```

### LLM 降级策略

```yaml
# config.yaml
llm:
  primary: zhipu          # 首选：智谱 GLM5
  fallbacks:
    - minimax             # 降级 1:MiniMax
    - skip                # 降级 2:跳过并记录
  quota_check:
    enabled: true         # 启用配额检查
    threshold: 100        # 配额低于此值时切换
```

### 失败笔记处理

```python
def handle_failed_note(note: dict, error: str):
    """处理失败的笔记"""
    failed_dir = Path(config.data_path) / "_failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    
    failed_file = failed_dir / f"{note['note_id']}.json"
    failed_file.write_text(json.dumps({
        "note": note,
        "error": error,
        "failed_at": datetime.now().isoformat(),
        "stage": current_stage  # ingest/digest/compile/publish
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    logger.error(f"笔记 {note['note_id']} 失败，已保存到 {failed_file}")
```

---

## 八、监控与通知

### 执行日志格式

```
[2026-04-13 03:00:00] ========== 开始每日知识生产线 ==========
[2026-04-13 03:00:01] [1/4] 摄取阶段：从 get 笔记 API 抽取新笔记...
[2026-04-13 03:05:30]   已抽取：120 条笔记
[2026-04-13 03:05:30]   成功：118 条，失败：2 条
[2026-04-13 03:05:30] ✓ 摄取阶段完成
[2026-04-13 03:05:31] [2/4] 消化阶段：生成标题和分类...
...
```

### 通知配置

```yaml
# config.yaml
notify:
  enabled: true
  channels:
    - type: email
      to: user@example.com
      on: [success, failure]  # 成功/失败时通知
    - type: wechat
      webhook: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
      on: [failure]           # 仅失败时通知
```

---

## 九、实施计划

### Phase 1: 目录重构（1 天）
- [ ] 创建新目录结构
- [ ] 移动现有数据
- [ ] 更新 config.yaml

### Phase 2: 脚本开发（3 天）
- [ ] 重构 `ingest.py`
- [ ] 创建 `digest.py`
- [ ] 创建 `apply_digest.py`
- [ ] 重构 `compiler.py`
- [ ] 创建 `publish.py`
- [ ] 创建 `daily_pipeline.sh`

### Phase 3: 状态追踪（1 天）
- [ ] 实现 `ProcessingStatus` 类
- [ ] 创建进度文件格式
- [ ] 添加幂等性检查

### Phase 4: 测试与部署（1 天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 配置 crontab
- [ ] 首次完整运行

---

## 十、配置总览

```yaml
# config.yaml - 完整配置
vault_path: /Users/qiming/ObsidianWiki
data_path: /Users/qiming/ObsidianWiki/processed
raw_path: /Users/qiming/ObsidianWiki/raw
logs_path: /Users/qiming/ObsidianWiki/logs

# 摄取配置
ingest:
  batch_size: 100
  rate_limit_delay: 2.0
  max_retries: 3

# 消化配置
digest:
  batch_size: 50
  rate_limit_delay: 1.0
  atomic_notes:
    enabled: true
    max_length: 2000
  auto_classify:
    enabled: true
    match_threshold: 0.8

# 编译配置
compile:
  batch_size: 15
  max_retries: 2
  default_provider: zhipu
  wikilinks:
    enabled: true
  aggregation:
    min_notes: 3
    topic_similarity: 0.7

# 输出配置
publish:
  enabled: true
  html_cards:
    enabled: true
    template: cards/default.html

# LLM 配置
llm:
  primary: zhipu
  fallbacks:
    - minimax
    - skip

# 通知配置
notify:
  enabled: true
  on: [success, failure]
```

---

## 参考

- [principle.md](../rules/principles.md) - 项目原则
- [knowledge-base-structure.md](../rules/knowledge-base-structure.md) - 知识库结构约束
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 系统架构
