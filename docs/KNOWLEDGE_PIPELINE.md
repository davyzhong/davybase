# Davybase 知识入库管线完整说明

**版本**: v5.0  
**创建日期**: 2026-04-17  
**状态**: 生产就绪

---

## 执行摘要

Davybase 是一条完整的 AI Native 知识生产线，将被困在 get 笔记 APP 中的碎片化知识，自动化转换为 Obsidian Wiki 格式的结构化知识。

### 核心价值主张

| 痛点 | 解决方案 |
|------|----------|
| 笔记 APP 信息孤岛 | 自动化导出 + 标准化格式 |
| 知识碎片化 | LLM 智能聚合 + 主题聚类 |
| 分类混乱 | 二次分类校准（16 分类体系） |
| 手动整理耗时 | 全自动化流水线，~76% 时间节省 |

### 五阶段管线总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Davybase 知识入库管线 (v5.0)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  前半段：知识收集与整理                    后半段：知识创作与输出         │
│  ┌─────────────────────────────┐        ┌─────────────────────────────┐ │
│  │  阶段 1    阶段 2    阶段 3   │        │  阶段 4        阶段 5       │ │
│  │  Ingest → Digest → Classify │   →    │  Compile  →  Publish        │ │
│  │  (抽取)   (消化)  (分类)     │        │  (编译)       (发布)        │ │
│  └─────────────────────────────┘        └─────────────────────────────┘ │
│           │                                        │                     │
│           ▼                                        ▼                     │
│     get 笔记 API                            Obsidian Wiki                │
│     raw/notes/                              wiki/{主题}.md               │
│     processed/{分类}/                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 两条 Skills 分工

| Skill | 职责 | 输入 | 输出 | 执行频率 |
|-------|------|------|------|----------|
| **get 笔记整理助手** | 知识收集与整理 | get 笔记 API | `processed/{16 分类}/` | 每日增量 |
| **Wiki 知识创作助手** | 知识创作与输出 | `processed/{分类}/` | `wiki/{主题}.md` | 按需/每周 |

---

## 前半段：知识收集与整理

### Skill 名称：`get 笔记整理助手`

**定位**: 每日增量收集，将 get 笔记 API 的原始笔记抽取、消化、分类到 16 个知识库目录

**执行频率**: 每日自动运行（建议早上 6 点）

**预期耗时**: 50-100 条笔记 ≈ 15-30 分钟

### 三段式处理流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  get 笔记整理助手 (前半段 Skill)                                         │
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
└─────────────────────────────────────────────────────────────────────────┘
```

### 阶段 1: Ingest（抽取）

**目标**: 从 get 笔记 API 抽取原始笔记

**输入**: get 笔记 API 凭据

**输出**: `raw/notes/_inbox/{note_id}.md`

**处理逻辑**:
1. 调用 get 笔记 API 获取笔记列表
2. 过滤已抽取的笔记（幂等性检查）
3. 并发抽取笔记内容（concurrency=3）
4. 保存为原始 Markdown 文件
5. 记录抽取状态到 SQLite

**配置参数**:
```yaml
ingest:
  batch_size: 20          # 单批次最大抽取数量
  concurrency: 3          # 并发请求数
  rate_limit_delay: 60s   # API 请求间隔（秒）
  resume: true            # 断点续传
```

---

### 阶段 2: Digest（消化）

**目标**: 为原始笔记生成标题、分类、原子化拆解

**输入**: `raw/notes/_inbox/*.md`

**输出**: 带 frontmatter 的 Markdown，包含：
- `title`: 生成的标题
- `category`: 初步分类
- `tags`: 自动标签
- `digest_at`: 处理时间戳

**处理逻辑**:
1. 读取原始笔记内容（前 3000 字符）
2. 调用 LLM（千问/MiniMax 轮询）生成：
   - 简洁标题（10-20 字）
   - 分类建议（从 16 分类体系选择）
   - 3-5 个关键词标签
3. 原子化拆解：识别笔记中的独立主题，必要时拆分为多条
4. 写入 frontmatter

**LLM 提示词示例**:
```
你是一个知识库助手。请阅读以下笔记内容，返回 JSON 格式：
1. title: 简洁准确的标题（10-20 字）
2. category: 从 16 分类中选择
3. tags: 3-5 个关键词标签

笔记内容：{content}

返回格式：{"title": "...", "category": "...", "tags": [...]}
```

**配置参数**:
```yaml
digest:
  batch_size: 10          # 单批次处理数量
  concurrency: 5          # 并发任务数
  provider_rotation: weighted  # 千问 45% / MiniMax 50% / 智谱 5%
```

---

### 阶段 3: Classify（二次分类）

**目标**: 校准 Digest 阶段的初步分类，确保笔记归入正确的知识库

**为什么需要二次分类**:
- Digest 阶段使用简化的提示词，分类精度有限
- 部分笔记内容复杂，需要更详细的分类规则
- 16 分类体系需要更精确的判断逻辑

**输入**: `processed/{初步分类}/*.md` 或 `raw/notes/_inbox/*.md`（未分类）

**输出**: 移动到正确的 `processed/{16 分类}/` 目录

**16 分类体系**:

| 新增知识库（6 个） | 现有知识库（10 个） |
|-------------------|-------------------|
| AI 与编程 | 编程+AI |
| 企业管理 | AI+ 机器学习 |
| 财务与会计 | 产品管理 |
| 跨境物流 | 系统架构 |
| 人文历史 | 后端开发 |
| 个人成长 | 前端开发 |
| | 数据库 |
| | DevOps |
| | 经营&管理 |
| | 学习&思考 |

**分类规则**:
1. 优先使用新增的 6 个知识库（更精确）
2. 如果内容同时符合多个分类，选择最具体的那个
3. 技术实现细节 → 对应技术库（如后端开发、前端开发）
4. 业务/流程/架构 → 对应业务库（如跨境物流、企业管理）
5. 个人感悟/通用知识 → 人文历史或个人成长

**处理逻辑**:
1. 扫描未分类或分类存疑的笔记
2. 使用双千问实例并发分类（concurrency=24）
3. 验证分类结果是否在 16 分类体系内
4. 移动到正确的分类目录
5. 记录分类状态

**配置参数**:
```yaml
classify:
  providers: ["qwen-1", "qwen-2"]  # 双千问实例
  concurrency: 12                  # 每个实例 12 并发
  batch_size: 5                    # 批次大小
```

---

### 前半段输出结构

```
processed/
├── AI 与编程/
│   ├── 1871069501047586224_.md
│   └── ...
├── 企业管理/
│   ├── 1871069771632630608_.md
│   └── ...
├── 财务与会计/
│   ├── 1871070070130752944_.md
│   └── ...
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

## 后半段：知识创作与输出

### Skill 名称：`Wiki 知识创作助手`

**定位**: 将已分类的 Markdown 笔记跨目录聚合，编译为结构化的 Wiki 条目

**执行频率**: 按需执行（建议每周 1-2 次，或当某个主题积累 10+ 条笔记时）

**预期耗时**: 100 条笔记 ≈ 5-10 分钟

### 两段式处理流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Wiki 知识创作助手 (后半段 Skill)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐   │
│  │         Compile              │    │          Publish             │   │
│  │         编译                 │    │          发布                │   │
│  └──────────────────────────────┘    └──────────────────────────────┘   │
│              │                                      │                    │
│              ▼                                      ▼                    │
│   processed/{16 分类}/                      wiki/{主题}.md               │
│   (已分类的 Markdown 笔记)                   (结构化 Wiki 条目)           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 阶段 4: Compile（编译）

**目标**: 跨目录聚合相关主题的笔记，编译为结构化 Wiki 条目

**核心理念**: **跨目录主题聚合**
- 不按分类目录机械分割
- 根据笔记内容主题智能聚类
- 相似主题的笔记聚合为同一个 Wiki 条目

**输入**: `processed/{16 分类}/*.md`

**输出**: `wiki/{主题}.md` - 结构化 Wiki 条目，包含：
- Frontmatter（title, source, tags, created, type）
- 核心摘要（200-300 字）
- 关键要点列表
- 双向链接 `[[links]]`
- 自动生成的内容块标记

**处理逻辑**:

#### 4.1 主题聚类
1. 扫描所有分类目录的笔记
2. 使用语义相似度算法（或 LLM）识别相似主题
3. 将笔记分组到主题簇（Theme Cluster）

**主题簇示例**:
```
主题簇："Agent 技术"
├── AI 与编程/Cursor AI 记忆功能解析.md
├── AI+ 机器学习/Agent Memory 技术对比.md
├── 产品管理/Agent 产品设计原则.md
└── 系统架构/Agent 系统架构模式.md
```

#### 4.2 LLM 编译
发送每个主题簇的笔记给 LLM，生成：
- 核心摘要（200-300 字概括）
- 关键概念列表（用于标签）
- 相关概念链接（用于双链）
- Wiki 条目结构

**LLM 提示词示例**:
```
你是一个知识库编辑。以下是多条相关笔记：

{notes_content}

请完成以下任务：
1. 为这些笔记聚合生成一个 Wiki 条目
2. 包含：核心摘要、关键要点、相关概念双链
3. 使用 Obsidian Flavored Markdown 格式
4. Frontmatter 包含：title, source, tags, created, type

返回格式：
---
title: 条目名称
source: get 笔记
tags: [tag1, tag2, tag3]
created: 2026-04-17
type: wiki_entry
---

%%davybase-auto-begin%%
## 核心摘要
...
## 关键概念
- [[概念 1]]
- [[概念 2]]
%%davybase-auto-end%%
```

#### 4.3 降级策略
```
1. 尝试 千问（配额充足，45% 权重）
2. 如果失败 → 切换到 MiniMax（50% 权重）
3. 如果仍然失败 → 智谱（5% 权重，保底）
4. 全部失败 → 跳过，记录错误
```

**配置参数**:
```yaml
compile:
  batch_size: 5              # 单批次笔记数量
  concurrent_batches: 2      # 同时编译的批次数量
  provider_rotation: weighted  # 千问 45% / MiniMax 50% / 智谱 5%
  threshold: 3               # 触发编译的最小笔记数（>=3 条才编译）
```

---

### 阶段 5: Publish（发布）

**目标**: 将编译好的 Wiki 条目写入 Obsidian，处理冲突和手动编辑保留

**输入**: 编译生成的 Wiki 草稿

**输出**: `wiki/{主题}.md` - 最终 Markdown 文件

**处理逻辑**:

#### 5.1 冲突检测
- 检查目标文件是否存在
- 如果存在，检测是否有手动编辑内容

#### 5.2 内容合并策略
```markdown
---
title: 条目名称
source: get 笔记
tags: [tag1, tag2, tag3]
created: 2026-04-17
type: wiki_entry
---

%%davybase-auto-begin%%
## 核心摘要
自动生成的摘要内容...
## 关键概念
- [[概念 1]]
- [[概念 2]]
%%davybase-auto-end%%

## 手动编辑部分
这部分内容不会被自动更新覆盖
用户可以在这里添加个人笔记、补充说明等
```

#### 5.3 写入策略
- 新文件：直接写入
- 已存在文件：
  - 保留 `%%davybase-auto-end%%` 之后的手动编辑内容
  - 更新 `%%davybase-auto-begin%%` 和 `%%davybase-auto-end%%` 之间的自动生成内容
  - 保留用户手动添加的 frontmatter 字段（如 `priority`, `status` 等）

**配置参数**:
```yaml
publish:
  vault_path: /Users/qiming/ObsidianWiki
  preserve_manual: true      # 保留手动编辑内容
  backup_before_overwrite: true  # 覆盖前备份
```

---

### 后半段输出结构

```
wiki/
├── Agent 技术全景.md
├── 跨境电商物流架构.md
├── 财务管理方法论.md
├── AI 编程工具对比.md
└── ...
```

---

## 两条 Skills 使用指南

### Skill 1: `get 笔记整理助手`

**触发词**:
- "从 get 笔记整理知识"
- "运行知识入库管线"
- "ingest notes from getnote"

**执行流程**:
```
用户：从 get 笔记整理知识

助手：好的，我将执行 get 笔记整理助手，包含以下步骤：
     1. Ingest: 从 get 笔记 API 抽取原始笔记
     2. Digest: 生成标题、分类、标签
     3. Classify: 二次分类校准到 16 个知识库

     检测到约 100 条待处理笔记，预计耗时 15-30 分钟。
     是否继续？(y/n)

用户：y

助手：[执行 pipeline...]
     ✅ 完成！
     - 抽取：100 条
     - 消化：100 条（千问 45 条，MiniMax 50 条，智谱 5 条）
     - 分类：98 条成功，2 条失败（分类置信度低，待人工审核）
     - 最终归档：processed/{16 分类}/
```

**幂等性保证**:
- 每次执行前检查已处理的笔记 ID
- 自动跳过已抽取、已消化、已分类的笔记
- 支持断点续传

---

### Skill 2: `Wiki 知识创作助手`

**触发词**:
- "将笔记编译成 Wiki"
- "运行知识创作管线"
- "compile notes to wiki"

**执行流程**:
```
用户：将笔记编译成 Wiki

助手：好的，我将执行 Wiki 知识创作助手，包含以下步骤：
     1. 扫描 processed/ 目录，识别主题簇
     2. Compile: 跨目录聚合相关笔记，编译为 Wiki 条目
     3. Publish: 写入 Obsidian，保留手动编辑内容

     检测到 500 条已分类笔记，可聚合为约 50 个 Wiki 条目。
     是否继续？(y/n)

用户：y

助手：[执行 pipeline...]
     ✅ 完成！
     - 主题聚类：识别 52 个主题簇
     - 编译：50 个 Wiki 条目（千问 23 条，MiniMax 25 条，智谱 2 条）
     - 发布：50 条成功，0 条失败
     - 输出：wiki/{主题}.md
```

**跨目录聚合示例**:
```
输入：processed/ 下的 500 条笔记（分布在 16 个分类目录）

主题聚类结果：
├── "Agent 技术" 主题簇（8 条笔记）
│   ├── AI 与编程/Cursor AI 记忆.md
│   ├── AI+ 机器学习/Agent Memory 对比.md
│   ├── 产品管理/Agent 产品设计.md
│   └── ...
├── "跨境物流" 主题簇（12 条笔记）
│   ├── 跨境物流/国际快递面单系统.md
│   ├── 企业管理/物流团队建设.md
│   └── ...
└── ...

输出：
├── wiki/Agent 技术全景.md
├── wiki/跨境物流架构.md
└── ...
```

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

### 状态字段说明

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
| **API 限流（429）** | 指数退避重试（10s, 20s, 40s, 60s, 60s），仍失败则跳过 |
| **LLM 配额不足** | 自动降级到下一个 Provider（千问→MiniMax→智谱） |
| **JSON 解析失败** | 使用备用分类（"未分类"），标记为待人工审核 |
| **网络超时** | 重试 3 次，仍失败则记录错误，支持断点续传 |
| **文件写入冲突** | 保留手动编辑内容，仅更新自动生成部分 |

### 失败恢复

```bash
# 查看失败项目
python main.py status --show-failed

# 重试失败项目
python main.py retry --stage ingest
python main.py retry --stage digest
python main.py retry --stage classify
python main.py retry --stage compile
```

---

## 配置总览

### config.yaml 完整配置

```yaml
# Davybase 配置文件 v5.0

# 路径配置
vault_path: /Users/qiming/ObsidianWiki
data_path: /Users/qiming/ObsidianWiki/processed
raw_path: /Users/qiming/ObsidianWiki/raw
logs_path: /Users/qiming/ObsidianWiki/logs
state_path: /Users/qiming/ObsidianWiki/.davybase

# 前半段：知识收集与整理
pipeline:
  # 阶段 1: Ingest（抽取）
  ingest:
    enabled: true
    batch_size: 20
    concurrency: 3
    rate_limit_delay: 60.0
    resume: true

  # 阶段 2: Digest（消化）
  digest:
    enabled: true
    batch_size: 10
    concurrency: 5
    provider_rotation: weighted
    providers:
      qwen:
        batch_size: 3
        weight: 0.45
      minimax:
        batch_size: 4
        weight: 0.50
      zhipu:
        batch_size: 1
        weight: 0.05

  # 阶段 3: Classify（二次分类）
  classify:
    enabled: true
    providers: ["qwen-1", "qwen-2"]
    concurrency: 12
    batch_size: 5

# 后半段：知识创作与输出
  # 阶段 4: Compile（编译）
  compile:
    enabled: true
    batch_size: 5
    concurrent_batches: 2
    provider_rotation: weighted
    threshold: 3

  # 阶段 5: Publish（发布）
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

## 附录：16 分类体系详细说明

### 新增知识库（6 个）

| 分类 | 内容范围 | 示例主题 |
|------|---------|---------|
| **AI 与编程** | AI 编程工具、MCP 协议、开发范式 | Cursor、Claude Code、n8n、Agent 开发 |
| **企业管理** | 业务管理、团队建设、组织变革 | 团队管理、经营分析、领导力 |
| **财务与会计** | 财务报表、财务分析、管理会计 | 财务报表分析、税务筹划、审计 |
| **跨境物流** | 国际快递、面单系统、供应链 | 跨境物流架构、国际快递流程 |
| **人文历史** | 历史典故、哲学思想、文化教育 | 中国历史、哲学思考、国学经典 |
| **个人成长** | 人生感悟、学习方法、心理健康 | 时间管理、学习方法、职业发展 |

### 现有知识库（10 个）

| 分类 | 内容范围 | 示例主题 |
|------|---------|---------|
| **编程+AI** | 编程与 AI 交叉内容 | AI 辅助编程、代码生成 |
| **AI+ 机器学习** | 人工智能算法、深度学习 | 机器学习算法、神经网络 |
| **产品管理** | 产品设计、产品规划 | 产品需求文档、竞品分析 |
| **系统架构** | 系统设计、架构模式 | 微服务架构、系统设计原则 |
| **后端开发** | 后端技术、服务器端开发 | Spring Boot、API 设计 |
| **前端开发** | 前端技术、Web 开发 | React、Vue、CSS |
| **数据库** | 数据库技术、SQL/NoSQL | MySQL、MongoDB、Redis |
| **DevOps** | 运维开发、CI/CD、容器化 | Docker、Kubernetes、Jenkins |
| **经营&管理** | 企业经营、管理方法论 | OKR、KPI、管理咨询 |
| **学习&思考** | 学习方法、思考模型 | 费曼学习法、思维模型 |

---

## 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构详细设计
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南
- [MCP_SERVER_GUIDE.md](MCP_SERVER_GUIDE.md) - MCP 服务器配置
- [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md) - 限流故障排查

---

## 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v5.0 | 2026-04-17 | 两条 Skills 重新设计，二次分类移入前半段 |
| v4.2 | 2026-04-14 | Worker 池模式、Provider 级别限流控制 |
| v4.0 | 2026-04-13 | 并发管线架构、多 LLM 负载均衡 |
| v3.0 | 2026-04-10 | AI Native 架构、MCP 协议支持 |
| v1.0 | 2026-04-01 | 初始版本 |
