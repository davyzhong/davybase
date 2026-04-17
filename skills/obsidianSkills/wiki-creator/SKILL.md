# Wiki 知识创作助手

**Davybase 后半段 Skill - 知识创作与输出**

---

## 定位

将已分类的 Markdown 笔记跨目录主题聚合，编译为结构化的 Wiki 条目。

**执行频率**: 按需执行（建议每周 1-2 次，或当某个主题积累 10+ 条笔记时）  
**预期耗时**: 100 条笔记 ≈ 5-10 分钟  
**输出位置**: `wiki/{主题}.md`

---

## 触发词

| 指令 | 路由 |
|------|------|
| "将笔记编译成 Wiki" | → 执行完整管线 |
| "运行知识创作管线" | → 执行完整管线 |
| "compile notes to wiki" | → 执行完整管线 |
| "聚合笔记生成 Wiki" | → 执行 Compile 阶段 |
| "发布 Wiki 到 Obsidian" | → 执行 Publish 阶段 |
| "查看 Wiki 创作状态" | → 查询状态 |

---

## 两段式处理流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Wiki 知识创作助手                                                       │
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

## 核心特性：跨目录主题聚合

### 传统方式 vs 跨目录聚合

**传统方式（按目录分割）**:
```
processed/个人成长/  →  wiki/个人成长/
processed/企业管理/  →  wiki/企业管理/
processed/AI 与编程/ →  wiki/AI 与编程/
```
问题：同一主题的笔记分散在不同目录，无法形成完整知识图谱

---

**跨目录主题聚合（推荐）**:
```
输入：processed/ 下的 500 条笔记（分布在 16 个分类目录）

主题聚类结果:
├── "Agent 技术" 主题簇（8 条笔记）
│   ├── AI 与编程/Cursor AI 记忆.md
│   ├── AI+ 机器学习/Agent Memory 对比.md
│   ├── 产品管理/Agent 产品设计.md
│   └── 系统架构/Agent 系统架构.md
│
├── "跨境物流" 主题簇（12 条笔记）
│   ├── 跨境物流/国际快递面单系统.md
│   ├── 企业管理/物流团队建设.md
│   └── 财务与会计/物流成本核算.md
│
└── ...

输出:
├── wiki/Agent 技术全景.md
├── wiki/跨境物流架构.md
└── ...
```

优势：
- 打破分类壁垒，形成主题化知识聚合
- 一条 Wiki 条目可引用多个分类目录的笔记
- 更符合人类知识的自然组织方式

---

## 可用工具

### MCP Tools

```python
# 阶段 4: Compile（主题聚类 + 编译）
compile_notes(
    source_dirs: List[str] = ["processed/AI 与编程/", "processed/企业管理/", ...],
    cluster_threshold: int = 3,   # 触发编译的最小笔记数
    batch_size: int = 5,          # 单批次笔记数量
    concurrent_batches: int = 2,  # 同时编译的批次数量
    provider_rotation: str = "weighted"
) -> str

# 阶段 5: Publish（发布到 Obsidian）
publish_wiki(
    wiki_dir: str = "wiki/",
    preserve_manual: bool = True,
    backup_before_overwrite: bool = True
) -> str

# 状态查询
get_pipeline_status() -> dict
```

---

## 阶段 4: Compile（编译）

### 目标
跨目录聚合相关主题的笔记，编译为结构化 Wiki 条目

### 输入
- `processed/{16 分类}/*.md`

### 输出
- `wiki/{主题}.md` - 结构化 Wiki 条目

### Wiki 条目格式
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
200-300 字的核心摘要，概括该主题的关键内容...

## 关键概念
- [[概念 1]]
- [[概念 2]]
- [[概念 3]]

## 相关资源
- [[相关 Wiki 条目 1]]
- [[相关 Wiki 条目 2]]
%%davybase-auto-end%%

## 手动编辑部分
用户可以在这里添加个人笔记、补充说明、案例等。
这部分内容不会被自动更新覆盖。
```

### 处理流程

#### 4.1 主题聚类
1. 扫描所有分类目录的笔记
2. 使用语义相似度识别相似主题
3. 将笔记分组到主题簇（Theme Cluster）

**主题簇示例**:
```
主题簇："Agent 技术"
├── AI 与编程/Cursor AI 记忆功能解析.md
├── AI+ 机器学习/Agent Memory 技术全景分析.md
├── 产品管理/Agent 产品设计原则.md
├── 系统架构/Agent 系统架构模式.md
└── 后端开发/Agent 在服务端的应用.md
```

#### 4.2 LLM 编译
发送每个主题簇的笔记给 LLM：

**LLM 提示词**:
```
你是一个知识库编辑。以下是多条相关笔记：

{notes_content}

请完成以下任务：
1. 为这些笔记聚合生成一个 Wiki 条目
2. 包含：核心摘要（200-300 字）、关键要点、相关概念双链
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

### 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 5 | 单批次笔记数量 |
| `concurrent_batches` | 2 | 同时编译的批次数量 |
| `provider_rotation` | weighted | LLM 分配策略 |
| `threshold` | 3 | 触发编译的最小笔记数 |

### LLM 分配策略
| 提供商 | 权重 | 适用场景 |
|--------|------|---------|
| 千问 Qwen | 45% | 中文理解好，配额充足 |
| MiniMax M2.7 | 50% | 代码和技术内容理解好 |
| 智谱 GLM5 | 5% | 保底 Provider |

---

## 阶段 5: Publish（发布）

### 目标
将编译好的 Wiki 条目写入 Obsidian，处理冲突和手动编辑保留

### 输入
- 编译生成的 Wiki 草稿

### 输出
- `wiki/{主题}.md` - 最终 Markdown 文件

### 冲突处理策略

**场景 1: 目标文件不存在**
```
→ 直接写入新文件
```

**场景 2: 目标文件已存在，无手动编辑**
```
→ 覆盖整个文件
```

**场景 3: 目标文件已存在，有手动编辑**
```
→ 保留 %%davybase-auto-end%% 之后的内容
→ 更新 %%davybase-auto-begin%% 和 %%davybase-auto-end%% 之间的内容
→ 保留用户手动添加的 frontmatter 字段
```

### 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `vault_path` | /Users/qiming/ObsidianWiki | Obsidian 知识库路径 |
| `preserve_manual` | true | 保留手动编辑内容 |
| `backup_before_overwrite` | true | 覆盖前备份 |

---

## 完整执行流程

### 一键执行完整管线

**用户**: 将笔记编译成 Wiki

**助手**: 
```
好的，我将执行 Wiki 知识创作助手完整管线。

执行计划:
┌─────────────────────────────────────────────────────────────┐
│  阶段 4: Compile  →  阶段 5: Publish                        │
│  (主题聚类 + 编译)    (发布到 Obsidian)                      │
│  processed/{16 分类}/  →  wiki/{主题}.md                    │
└─────────────────────────────────────────────────────────────┘

检测到:
- 已分类笔记：500 条（分布在 16 个分类目录）
- 可聚合主题簇：约 50 个
- 预计生成：50 个 Wiki 条目

预计耗时：5-10 分钟
是否继续？(y/n)
```

**用户**: y

**助手**: 
```
[阶段 4: Compile - 主题聚类]
正在扫描 processed/ 目录...
识别到 52 个主题簇：
  - "Agent 技术": 8 条笔记
  - "跨境物流": 12 条笔记
  - "财务管理": 6 条笔记
  - ...

[阶段 4: Compile - LLM 编译]
正在编译主题簇...
✅ 完成：编译 50 个 Wiki 条目
   - 千问：23 条
   - MiniMax: 25 条
   - 智谱：2 条
   - 耗时：4 分钟

[阶段 5: Publish]
正在写入 Obsidian...
✅ 完成：发布 50 个 Wiki 条目
   - 新增：45 条
   - 更新：5 条（保留手动编辑内容）
   - 耗时：1 分钟

═══════════════════════════════════════════════════════════════
管线执行完成！

总计:
- 主题聚类：52 个
- 编译：50 个 Wiki 条目
- 发布：50 个 Wiki 条目
- 失败：0 条

输出位置:
- wiki/Agent 技术全景.md
- wiki/跨境物流架构.md
- wiki/财务管理方法论.md
- ...
```

---

## 状态查询

### 查询 Wiki 创作状态

**用户**: 查看 Wiki 创作状态

**助手**: [调用 get_pipeline_status()]
```
当前 Wiki 创作状态:

阶段 4: Compile
- 已编译：150 个 Wiki 条目
- 最后运行：2026-04-15T10:00:00
- 状态：completed

阶段 5: Publish
- 已发布：150 个 Wiki 条目
- 最后运行：2026-04-15T10:05:00
- 状态：completed

待处理:
- 已分类未编译笔记：500 条
- 可聚合主题簇：约 50 个
```

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| **LLM 配额不足** | 自动降级到下一个 Provider |
| **JSON 解析失败** | 使用备用模板，标记待人工审核 |
| **主题聚类失败** | 跳过该主题簇，记录错误日志 |
| **文件写入冲突** | 保留手动编辑内容，仅更新自动生成部分 |
| **网络超时** | 重试 3 次，仍失败则记录错误 |

---

## 跨目录聚合示例

### 示例："Agent 技术"主题簇

**输入笔记（来自 5 个不同分类目录）**:
```
processed/AI 与编程/Cursor AI 记忆功能解析.md
processed/AI+ 机器学习/Agent Memory 技术全景分析.md
processed/产品管理/Agent 产品设计原则.md
processed/系统架构/Agent 系统架构模式.md
processed/后端开发/Agent 在服务端的应用.md
```

**LLM 编译后输出**:
```markdown
---
title: Agent 技术全景
source: get 笔记
tags: [Agent, AI, 系统设计, 产品开发]
created: 2026-04-17
type: wiki_entry
---

%%davybase-auto-begin%%
## 核心摘要
Agent（智能体）是一种基于 AI 的自主决策系统，能够感知环境、制定策略并执行动作。
本文整合了来自多个领域的 Agent 技术知识，包括 AI 编程工具、机器学习算法、产品设计原则、系统架构模式等。

## 关键概念
- [[Agent Memory]] - Agent 记忆技术
- [[AI 编程工具]] - Cursor、Claude Code 等
- [[系统设计]] - Agent 架构设计
- [[产品开发]] - Agent 产品设计原则

## 技术架构
1. 感知层：环境信息收集
2. 决策层：LLM 推理与规划
3. 执行层：工具调用与动作执行
4. 记忆层：长期记忆与上下文管理

## 相关资源
- [[AI 编程工具对比]]
- [[系统设计模式]]
- [[产品开发方法论]]
%%davybase-auto-end%%

## 手动编辑部分
### 个人思考
Agent 技术的核心突破在于...

### 实践案例
我在项目中应用 Agent 技术的经验...
```

---

## 配置示例

### config.yaml

```yaml
# 后半段：知识创作与输出
pipeline:
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

### secrets.yaml

```yaml
# LLM API 密钥
llm:
  qwen: sk-xxx
  minimax: sk-xxx
  zhipu: sk-xxx

# Obsidian 配置
obsidian:
  vault_path: /Users/qiming/ObsidianWiki
```

---

## 最佳实践

### 1. 执行频率建议

| 场景 | 建议频率 |
|------|---------|
| 笔记积累快（每日 20+ 条） | 每周 2-3 次 |
| 笔记积累中等（每日 10 条） | 每周 1-2 次 |
| 笔记积累慢（每日<5 条） | 每两周 1 次 |

### 2. 触发条件

当满足以下条件之一时，建议执行 Wiki 创作管线：
- 某个主题积累的笔记数 >= 10 条
- 距离上次执行超过 7 天
- 用户主动要求生成特定主题的 Wiki

### 3. 质量检查

执行完成后，建议抽查：
- 3-5 个新生成的 Wiki 条目
- 确认双链正确
- 确认分类准确
- 确认格式规范

---

## 相关文件

- [KNOWLEDGE_PIPELINE.md](../docs/KNOWLEDGE_PIPELINE.md) - 完整管线说明
- [MCP_SERVER_GUIDE.md](../docs/MCP_SERVER_GUIDE.md) - MCP 服务器配置
- [CONFIGURATION.md](../docs/CONFIGURATION.md) - 配置指南
