# Davybase v5.0 架构设计文档

**版本**: v5.0  
**创建日期**: 2026-04-17  
**状态**: 生产就绪

---

## 执行摘要

Davybase v5.0 是对原 v4.2 架构的重大重构，核心变更是**将知识入库管线拆分为两条独立的 Skills**，并将二次分类阶段移入前半段。

### 核心设计决策

| 决策 | 理由 | 效果 |
|------|------|------|
| **两条 Skills 分工** | 职责分离：前半段负责"整理"，后半段负责"创作" | 可独立运行，灵活性高 |
| **二次分类移入前半段** | 二次分类是"整理"工作，不是"创作"工作 | 前半段结束时数据已干净 |
| **跨目录主题聚合** | 打破分类壁垒，按主题聚类 | Wiki 条目更完整、更系统 |

---

## 架构对比：v4.2 vs v5.0

### v4.2 架构（四阶段单管线）

```
┌─────────────────────────────────────────────────────────────┐
│  单一线程：Ingest → Digest → Compile → Publish               │
└─────────────────────────────────────────────────────────────┘
```

问题：
- 职责边界模糊：Digest 和 Compile 都涉及分类
- 无法独立运行：必须完整执行整个管线
- 错误耦合：某一阶段失败影响后续所有阶段

---

### v5.0 架构（两条 Skills）

```
┌─────────────────────────────────────────────────────────────┐
│  前半段：get 笔记整理助手                                     │
│  Ingest → Digest → Classify                                 │
│  (抽取)    (消化)   (二次分类)                               │
│           │                                                 │
│           ▼                                                 │
│     processed/{16 分类}/                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  后半段：Wiki 知识创作助手                                    │
│  Compile → Publish                                          │
│  (跨目录主题聚合) (发布)                                     │
│           │                                                 │
│           ▼                                                 │
│     wiki/{主题}.md                                          │
└─────────────────────────────────────────────────────────────┘
```

优势：
- 职责清晰：前半段整理，后半段创作
- 独立运行：可只执行前半段或后半段
- 错误隔离：某条 Skill 失败不影响另一条

---

## 五阶段管线详解

### 阶段分解

```
┌─────────────────────────────────────────────────────────────────────────┐
│  get 笔记整理助手 (前半段 Skill)         Wiki 知识创作助手 (后半段 Skill)  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │   Ingest     │ ──> │    Digest    │ ──> │  Classify    │             │
│  │   抽取       │     │    消化      │     │  二次分类    │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│        │                    │                    │                       │
│        ▼                    ▼                    ▼                       │
│  raw/notes/_inbox/    processed/{初步}/   processed/{16 分类}/           │
│  (原始 Markdown)     (带标题分类)        (最终归档位置)                  │
│                                                                         │
│                                                  │                      │
│                                                  ▼                      │
│                                    ┌──────────────────────────────┐     │
│                                    │         Compile              │     │
│                                    │         编译                 │     │
│                                    └──────────────────────────────┘     │
│                                                 │                        │
│                                                 ▼                        │
│                                    ┌──────────────────────────────┐     │
│                                    │         Publish              │     │
│                                    │         发布                 │     │
│                                    └──────────────────────────────┘     │
│                                                 │                        │
│                                                 ▼                        │
│                                          wiki/{主题}.md                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段 1: Ingest（抽取）

### 职责
从 get 笔记 API 抽取原始笔记

### 技术实现
- **模块**: `src/orchestrator.py::IngestOrchestrator`
- **并发度**: 3（可配置）
- **速率限制**: 60 秒/请求（可配置）

### 幂等性检查
```python
if state.is_extracted(note_id):
    logger.info(f"跳过已抽取笔记：{note_id}")
    continue
```

### 输出
```
raw/notes/_inbox/
├── 1871069501047586224_.md
├── 1871069771632630608_.md
└── ...
```

---

## 阶段 2: Digest（消化）

### 职责
为原始笔记生成标题、分类、标签

### 技术实现
- **模块**: `src/orchestrator.py::DigestOrchestrator`
- **并发度**: 5（可配置）
- **LLM 分配**: 加权轮询（千问 45%、MiniMax 50%、智谱 5%）

### LLM 提示词
```
你是一个知识库助手。请阅读以下笔记内容，返回 JSON 格式：
1. title: 简洁准确的标题（10-20 字）
2. category: 从 16 分类中选择
3. tags: 3-5 个关键词标签

笔记内容：{content}

返回格式：{"title": "...", "category": "...", "tags": [...]}
```

### 输出
```markdown
---
title: 生成的标题
category: 初步分类
tags: [tag1, tag2, tag3]
digest_at: 2026-04-17T07:10:00
---

笔记内容...
```

---

## 阶段 3: Classify（二次分类）

### 职责
校准 Digest 阶段的初步分类，确保笔记归入正确的 16 分类知识库

### 为什么需要二次分类
1. Digest 阶段使用简化的提示词，分类精度有限
2. 部分笔记内容复杂，需要更详细的分类规则
3. 16 分类体系需要更精确的判断逻辑

### 技术实现
- **模块**: `src/reclassify_unclassified.py::UnclassifiedReclassifier`
- **并发度**: 24（双千问实例，每个 12 并发）
- **处理速度**: ~40 条/分钟

### 16 分类体系

**新增知识库（6 个）**:
- AI 与编程、企业管理、财务与会计、跨境物流、人文历史、个人成长

**现有知识库（10 个）**:
- 编程+AI、AI+ 机器学习、产品管理、系统架构、后端开发、前端开发、数据库、DevOps、经营&管理、学习&思考

### 分类规则
1. 优先使用新增的 6 个知识库（更精确）
2. 如果内容同时符合多个分类，选择最具体的那个
3. 技术实现细节 → 对应技术库
4. 业务/流程/架构 → 对应业务库
5. 个人感悟/通用知识 → 人文历史或个人成长

### 输出
```
processed/
├── AI 与编程/
├── 企业管理/
├── 财务与会计/
├── 跨境物流/
├── 人文历史/
├── 个人成长/
├── 编程+AI/
├── AI+ 机器学习/
├── 产品管理/
├── 系统架构/
├── 后端开发/
├── 前端开发/
├── 数据库/
├── DevOps/
├── 经营&管理/
└── 学习&思考/
```

---

## 阶段 4: Compile（编译）

### 职责
跨目录聚合相关主题的笔记，编译为结构化 Wiki 条目

### 核心特性：跨目录主题聚合

**传统方式（按目录分割）**:
```
processed/个人成长/  →  wiki/个人成长/
processed/企业管理/  →  wiki/企业管理/
```

**v5.0 方式（跨目录聚合）**:
```
输入：500 条笔记（分布在 16 个分类目录）

主题聚类结果:
├── "Agent 技术" 主题簇（8 条笔记）
│   ├── AI 与编程/Cursor AI 记忆.md
│   ├── AI+ 机器学习/Agent Memory 对比.md
│   ├── 产品管理/Agent 产品设计.md
│   └── 系统架构/Agent 系统架构.md

输出:
└── wiki/Agent 技术全景.md
```

### 技术实现
- **模块**: `src/compiler.py::Compiler`
- **批次大小**: 5 条笔记/批
- **并发批次**: 2（可配置）
- **LLM 分配**: 加权轮询（千问 45%、MiniMax 50%、智谱 5%）

### LLM 提示词
```
你是一个知识库编辑。以下是多条相关笔记：

{notes_content}

请完成以下任务：
1. 为这些笔记聚合生成一个 Wiki 条目
2. 包含：核心摘要（200-300 字）、关键要点、相关概念双链
3. 使用 Obsidian Flavored Markdown 格式
4. Frontmatter 包含：title, source, tags, created, type
```

### 输出格式
```markdown
---
title: Agent 技术全景
source: get 笔记
tags: [Agent, AI, 系统设计]
created: 2026-04-17
type: wiki_entry
---

%%davybase-auto-begin%%
## 核心摘要
Agent（智能体）是一种基于 AI 的自主决策系统...

## 关键概念
- [[Agent Memory]]
- [[AI 编程工具]]
- [[系统设计]]
%%davybase-auto-end%%

## 手动编辑部分
用户可以在这里添加个人笔记、补充说明等。
```

---

## 阶段 5: Publish（发布）

### 职责
将编译好的 Wiki 条目写入 Obsidian，处理冲突和手动编辑保留

### 技术实现
- **模块**: `src/writer.py::Writer`
- **冲突处理**: 保留 `%%davybase-auto-end%%` 之后的手动编辑内容
- **备份策略**: 覆盖前自动备份

### 冲突处理策略

| 场景 | 处理方式 |
|------|---------|
| 目标文件不存在 | 直接写入新文件 |
| 目标文件已存在，无手动编辑 | 覆盖整个文件 |
| 目标文件已存在，有手动编辑 | 保留手动编辑部分，仅更新自动生成块 |

---

## 状态追踪系统

### 状态文件结构

```
.davybase/
├── status/
│   ├── ingest.json       # Ingest 阶段状态
│   ├── digest.json       # Digest 阶段状态
│   ├── classify.json     # Classify 阶段状态
│   ├── compile.json      # Compile 阶段状态
│   └── publish.json      # Publish 阶段状态
└── progress/
    └── processing_status.json  # 总体进度
```

### 状态字段示例

```json
{
  "note_id": "1871069501047586224",
  "ingest": {
    "is_extracted": true,
    "extracted_at": "2026-04-17T07:00:00",
    "source_path": "raw/notes/_inbox/1871069501047586224_.md"
  },
  "digest": {
    "is_summarized": true,
    "summarized_at": "2026-04-17T07:10:00",
    "title": "生成的标题",
    "provider": "qwen"
  },
  "classify": {
    "is_classified": true,
    "classified_at": "2026-04-17T07:15:00",
    "category": "个人成长",
    "final_path": "processed/个人成长/1871069501047586224_.md"
  },
  "compile": {
    "is_compiled": false,
    "wiki_path": null
  },
  "publish": {
    "is_published": false,
    "published_path": null
  }
}
```

---

## 错误处理与降级

### 错误类型与处理策略

| 错误类型 | 处理策略 |
|---------|---------|
| **API 限流（429）** | 指数退避重试（10s, 20s, 40s, 60s, 60s） |
| **LLM 配额不足** | 自动降级到下一个 Provider |
| **JSON 解析失败** | 使用备用分类（"待审核"），标记待人工处理 |
| **网络超时** | 重试 3 次，仍失败则记录错误 |
| **分类置信度低** | 标记为"待人工审核"，不自动移动 |
| **文件写入冲突** | 保留手动编辑内容，仅更新自动生成部分 |

### 降级策略

```python
async def compile_with_fallback(notes, providers=["qwen", "minimax", "zhipu"]):
    for provider_name in providers:
        try:
            return await providers[provider_name].compile(notes)
        except Exception as e:
            logger.warning(f"{provider_name} 失败：{e}")
            continue
    
    raise RuntimeError("所有 LLM 提供商均失败")
```

---

## 性能指标

### 处理速度 benchmark（100 条笔记）

| 阶段 | 串行模式 | 并发模式 (v5.0) | 提升 |
|------|---------|---------------|------|
| Ingest | ~200 秒 | ~40 秒 | 80% |
| Digest | ~300 秒 | ~60 秒 | 80% |
| Classify | ~600 秒 | ~150 秒 | 75% |
| Compile | ~180 秒 | ~60 秒 | 67% |
| Publish | ~50 秒 | ~30 秒 | 40% |
| **总计** | ~1330 秒 | ~340 秒 | **~74%** |

### 成功率指标

| 阶段 | 目标成功率 | 实际表现 |
|------|-----------|---------|
| Ingest | >99% | ~99.5% |
| Digest | >95% | ~97% |
| Classify | >95% | ~96% |
| Compile | >90% | ~93% |
| Publish | >99% | ~99.5% |

---

## Skills 设计

### get 笔记整理助手（前半段）

**定位**: 每日增量收集，15-30 分钟处理 50-100 条笔记

**执行频率**: 每日自动运行（建议早上 6 点）

**输出位置**: `processed/{16 分类}/`

**触发词**:
- "从 get 笔记整理知识"
- "运行知识入库管线"
- "ingest notes from getnote"

---

### Wiki 知识创作助手（后半段）

**定位**: 按需执行，5-10 分钟将 100 条笔记编译为 Wiki

**执行频率**: 每周 1-2 次，或当某个主题积累 10+ 条笔记时

**输出位置**: `wiki/{主题}.md`

**触发词**:
- "将笔记编译成 Wiki"
- "运行知识创作管线"
- "compile notes to wiki"

---

## 配置示例

### config.yaml

```yaml
# 前半段：知识收集与整理
pipeline:
  ingest:
    enabled: true
    batch_size: 20
    concurrency: 3
    rate_limit_delay: 60.0
    resume: true

  digest:
    enabled: true
    batch_size: 10
    concurrency: 5
    provider_rotation: weighted

  classify:
    enabled: true
    providers: ["qwen-1", "qwen-2"]
    concurrency: 12
    batch_size: 5

# 后半段：知识创作与输出
  compile:
    enabled: true
    batch_size: 5
    concurrent_batches: 2
    provider_rotation: weighted
    threshold: 3

  publish:
    enabled: true
    preserve_manual: true
    backup_before_overwrite: true

# LLM 提供商配置
llm:
  default: qwen
  rotation_order: [qwen, minimax, zhipu]
  weights:
    qwen: 0.45
    minimax: 0.50
    zhipu: 0.05
```

---

## 相关文档

- [KNOWLEDGE_PIPELINE.md](KNOWLEDGE_PIPELINE.md) - 完整知识入库管线说明
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - Skills 使用指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 原系统架构文档（v4.2 及之前）
- [CONCURRENT_PIPELINE.md](CONCURRENT_PIPELINE.md) - 并发管线设计文档
- [WORKER_POOL_IMPLEMENTATION.md](WORKER_POOL_IMPLEMENTATION.md) - Worker 池模式实施文档

---

## 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v5.0 | 2026-04-17 | 两条 Skills 重新设计，二次分类移入前半段，跨目录主题聚合 |
| v4.2 | 2026-04-14 | Worker 池模式、Provider 级别限流控制 |
| v4.0 | 2026-04-13 | 并发管线架构、多 LLM 负载均衡 |
| v3.0 | 2026-04-10 | AI Native 架构、MCP 协议支持 |
| v1.0 | 2026-04-01 | 初始版本 |
