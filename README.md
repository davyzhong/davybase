# Davybase

> AI Native 知识生产线 - get 笔记 → Markdown → 二次分类 → Wiki 编译 → Obsidian

受 [Karpathy 的个人知识库 wiki 方案](https://karpathy.ai/llmcookbook/) 启发，Davybase 帮助你将被困在 get 笔记 APP 中的知识自动化导出，经过三段式整理和两段式创作，最终编译为带双向链接的结构化 wiki，发布到 Obsidian。

**v5.0 新特性**: 两条 Skills 分工、二次分类移入前半段、跨目录主题聚合！

**v4.2 核心架构**: Worker 池模式、Provider 级别限流控制、~76% 时间节省！

---

## 快速开始

### 📌 重要：首次使用必读

Davybase 采用 **"一次性全量 + 每日增量"** 工作流：

| 步骤 | 操作 | 频率 | 说明 |
|------|------|------|------|
| **第 1 步** | 全量同步 | **仅一次** | 首次使用时处理所有历史笔记 |
| **第 2 步** | 增量同步 | **每日自动** | 仅处理新增/修改的笔记 |

**新手指引**: 详细说明见 [docs/INITIALIZATION.md](docs/INITIALIZATION.md)

---

### 方式 1: AI Native Skills（推荐 - v5.0）

```bash
# 1. 配置 MCP 服务器
# 编辑 ~/.claude/settings.json 添加:
{
  "mcpServers": {
    "davybase": {
      "command": "python",
      "args": ["/Users/qiming/workspace/davybase/src/mcp_server.py"]
    }
  }
}

# 2. 使用自然语言交互

# 第 1 步：首次全量同步（仅执行一次）
/getnote-organizer     # 前半段：知识收集与整理
/wiki-creator          # 后半段：知识创作与输出

# 第 2 步：每日增量同步（设置定时任务自动执行）
# 见 docs/CRON_SETUP.md 配置每天早上 6 点自动运行
```

**两条 Skills 分工**:
| Skill | 职责 | 频率 | 输出 |
|-------|------|------|------|
| **get 笔记整理助手** | 知识收集与整理 | 每日自动 | `processed/{16 分类}/` |
| **Wiki 知识创作助手** | 知识创作与输出 | 每周 1-2 次 | `wiki/{主题}.md` |

### 方式 2: 并发 CLI (v4.2)

```bash
# 第 1 步：首次全量同步（仅执行一次）
python main.py pipeline --full --resume

# 第 2 步：每日增量同步（设置定时任务）
# 见 docs/CRON_SETUP.md 配置每天早上 6 点自动运行
python main.py incremental
```

**Worker 池模式说明**:
- 3 个 Worker 同时处理（千问、智谱、MiniMax 各一个）
- 每个 Worker 独立领取任务，处理完立即领取下一批
- 自动限流控制：智谱 60s 间隔，千问/MiniMax 3s 间隔
- 实时进度追踪：显示每个模型的 ✓/✗ 计数

### 方式 3: 传统 CLI

```bash
# 安装依赖
pip install -r requirements.txt

# 配置凭据（首次使用）
/note config

# 第 1 步：首次全量同步（仅执行一次）
python main.py full-sync --provider zhipu

# 第 2 步：每日增量同步（设置定时任务）
python main.py incremental --provider zhipu
# 见 docs/CRON_SETUP.md 配置每天早上 6 点自动运行
```

---

## 五阶段管线架构

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
│     processed/{16 分类}/                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 各阶段职责

| 阶段 | 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| **Ingest** | `src/orchestrator.py` | 从 get 笔记 API 抽取 | API 凭据 | `raw/notes/_inbox/` |
| **Digest** | `src/orchestrator.py` | 生成标题、初步分类 | 原始 Markdown | 带 frontmatter |
| **Classify** | `src/reclassify_unclassified.py` | 二次分类校准 | 初步分类笔记 | `processed/{16 分类}/` |
| **Compile** | `src/compiler.py` | 跨目录主题聚合 | 已分类笔记 | Wiki 草稿 |
| **Publish** | `src/writer.py` | 写入 Obsidian | Wiki 草稿 | `wiki/{主题}.md` |

---

## 功能特性

### v5.0 新增 (2026-04-17)

- **两条 Skills 分工** - get 笔记整理助手（前半段）+ Wiki 知识创作助手（后半段）
- **二次分类移入前半段** - 分类校准作为整理工作的一部分
- **跨目录主题聚合** - Wiki 编译打破分类壁垒，按主题聚类
- **16 分类体系** - 6 个新增知识库 + 10 个现有知识库

### v4.2 核心特性 (2026-04-14)

- **Worker 池模式** - 真正的流水线作业，每个 LLM 独立 Worker，处理完立即领取下一批
- **Provider 级别限流控制** - 每个 API 独立配置请求间隔，解决 TPM 配额差异问题
- **动态批次调整** - 根据处理速度自动调整批次大小，触发限流时自动减半
- **模型级进度追踪** - 实时显示每个模型的 ✓/✗ 计数和性能统计
- **限流缓解策略** - 加权轮询、批次衰减、冷却时间，多层防护避免 API 封禁

### v4.0 核心架构 (2026-04-13)

- **并发管线架构** - 分批次、并发执行，~76% 时间节省
- **多 LLM 负载均衡** - 轮询分配智谱、千问、MiniMax，减少单点限流影响
- **AI Native 架构** (v3.0) - 支持自然语言交互，无需记忆命令
- **MCP 协议** - 标准 Model Context Protocol，可与其他 AI 工具集成
- **Claude Skills** - 预定义技能，一键执行复杂任务
- **定时自动执行** - Claude Cron 调度，每日自动更新知识库

---

## 16 分类体系

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

| 分类 | 内容范围 |
|------|---------|
| **编程+AI** | 编程与 AI 交叉内容 |
| **AI+ 机器学习** | 人工智能算法、深度学习 |
| **产品管理** | 产品设计、产品规划 |
| **系统架构** | 系统设计、架构模式 |
| **后端开发** | 后端技术、服务器端开发 |
| **前端开发** | 前端技术、Web 开发 |
| **数据库** | 数据库技术、SQL/NoSQL |
| **DevOps** | 运维开发、CI/CD、容器化 |
| **经营&管理** | 企业经营、管理方法论 |
| **学习&思考** | 学习方法、思考模型 |

---

## 核心特性详解

### 跨目录主题聚合

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

---

## 配置

详细配置说明请参阅 [docs/CONFIGURATION.md](docs/CONFIGURATION.md) 和 [docs/SECRETS_SETUP.md](docs/SECRETS_SETUP.md)。

### 1. 配置 API 密钥

**方式 1（推荐）：** 复制 `secrets.example.yaml` 为 `secrets.yaml` 并填入密钥

```bash
cp secrets.example.yaml secrets.yaml
# 编辑 secrets.yaml，填入你的 API 密钥
chmod 600 secrets.yaml
```

**方式 2：** 使用环境变量

```bash
export GETNOTE_API_KEY=gk_live_xxx
export GETNOTE_CLIENT_ID=cli_xxx
export ZHIPU_API_KEY=your_zhipu_api_key
export MINIMAX_API_KEY=your_minimax_api_key
```

### 2. 配置 Obsidian Vault 路径

编辑 `config.yaml`：

```yaml
vault_path: /Users/qiming/ObsidianWiki  # 你的 Obsidian vault 路径
data_path: /Users/qiming/ObsidianWiki/processed
raw_path: /Users/qiming/ObsidianWiki/raw
logs_path: /Users/qiming/ObsidianWiki/logs
```

---

## Wiki 条目格式

```markdown
---
title: 反向传播算法
source:
  - data/raw/深度学习/note_12345.md
  - data/raw/深度学习/note_12346.md
tags: [深度学习，神经网络，算法]
created: 2026-04-11
type: wiki
---

# 反向传播算法

%%davybase-auto-begin%%
## 核心摘要
反向传播算法是神经网络训练的核心，通过链式法则计算梯度...

## 关键概念
- [[梯度下降]]
- [[链式法则]]
- [[自动微分]]
%%davybase-auto-end%%

## 手动编辑部分
这部分内容不会被自动更新覆盖，可以添加个人笔记、案例等。

## 相关笔记
- [[Transformer 模型]]
- [[注意力机制]]
```

自动生成的内容用 `%%davybase-auto-begin%%` / `%%davybase-auto-end%%` 包裹，重新同步时仅更新标记之间的内容，手动编辑会被保留。

---

## 定时同步

```bash
# 每天早上 6 点执行前半段管线（crontab）
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py pipeline --前半段 >> logs/sync.log 2>&1

# 每周日上午 10 点执行后半段管线
0 10 * * 0 cd /Users/qiming/workspace/davybase && python main.py pipeline --后半段 >> logs/sync.log 2>&1
```

---

## 文档

### 核心文档
- **[INITIALIZATION.md](docs/INITIALIZATION.md)** - 🆕 新手指引：首次使用必读（一次性全量 + 每日增量）
- **[KNOWLEDGE_PIPELINE.md](docs/KNOWLEDGE_PIPELINE.md)** - 完整知识入库管线说明（v5.0）
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系统架构（四阶段管线、模块设计、数据库结构）
- **[SKILLS_GUIDE.md](docs/SKILLS_GUIDE.md)** - Skills 使用指南（触发词、配置、最佳实践）

### 配置与使用
- **[SECRETS_SETUP.md](docs/SECRETS_SETUP.md)** - 密钥配置指南（API 密钥获取和配置方法）
- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - 完整配置指南（config.yaml、CLI 参数）
- **[USAGE.md](docs/USAGE.md)** - 使用指南（快速开始、常见工作流、故障排查）

### 架构与设计
- **[CONCURRENT_PIPELINE.md](docs/CONCURRENT_PIPELINE.md)** - 并发管线设计文档
- **[WORKER_POOL_IMPLEMENTATION.md](docs/WORKER_POOL_IMPLEMENTATION.md)** - Worker 池模式实施文档
- **[RATE_LIMIT_TROUBLESHOOTING.md](docs/RATE_LIMIT_TROUBLESHOOTING.md)** - 限流故障排查

### MCP 与自动化
- **[MCP_SERVER_GUIDE.md](docs/MCP_SERVER_GUIDE.md)** - MCP Server 配置指南
- **[CRON_SETUP.md](docs/CRON_SETUP.md)** - 定时任务配置指南

---

## 项目结构

```
davybase/
├── main.py                 # CLI 入口
├── config.yaml             # 配置文件
├── requirements.txt        # Python 依赖
├── src/
│   ├── orchestrator.py     # 并发管线编排器 (v4.0/v4.2/v5.0)
│   ├── extractor.py        # get 笔记 API 抽取
│   ├── converter.py        # markitdown 格式转换
│   ├── compiler.py         # LLM 编译（多提供商）
│   ├── writer.py           # Obsidian 写入
│   ├── reclassify_unclassified.py  # 二次分类脚本
│   ├── sync_state.py       # SQLite 状态管理
│   ├── processing_status.py # 状态追踪系统
│   ├── config.py           # 配置加载
│   ├── utils.py            # 工具函数
│   └── llm_providers/
│       ├── base.py         # LLMProvider 基类
│       ├── zhipu.py        # 智谱 GLM5
│       ├── minimax.py      # MiniMax M2.7
│       └── qwen.py         # 千问 Qwen
├── data/
│   ├── raw/                # 原始笔记暂存区（.gitignore）
│   └── sync.db             # SQLite 数据库（.gitignore）
├── logs/                   # 日志文件（.gitignore）
├── wiki/                   # Obsidian Wiki 输出（.gitignore）
├── tests/                  # 单元测试
├── skills/
│   └── obsidianSkills/
│       ├── getnote-organizer/  # get 笔记整理助手 (v5.0)
│       └── wiki-creator/       # Wiki 知识创作助手 (v5.0)
└── docs/
    ├── KNOWLEDGE_PIPELINE.md   # 完整管线说明 (v5.0)
    ├── ARCHITECTURE.md         # 系统架构
    ├── SKILLS_GUIDE.md         # Skills 使用指南
    └── ...
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

## 依赖

- `httpx>=0.27` — 异步 HTTP 客户端
- `click>=8.0` — CLI 框架
- `pyyaml>=6.0` — YAML 配置解析
- `markitdown>=0.1.0` — Microsoft 格式转 Markdown 工具
- `sqlite3` — 标准库，状态跟踪

---

## 安全

- API 密钥配置在 `secrets.yaml` 文件中（已加入 `.gitignore`），或存储在环境变量中
- `.gitignore` 已配置排除敏感文件和数据
- 原始笔记数据不污染 Obsidian vault，只有编译后的 wiki 条目写入

---

## 开发

```bash
# 运行测试
pytest

# 运行特定测试
pytest tests/test_writer.py -v

# 查看测试覆盖
pytest --cov=src --cov-report=term-missing
```

---

## 许可证

MIT

---

## 致谢

- 灵感来自 [Andrej Karpathy 的个人知识库](https://karpathy.ai/llmcookbook/)
- 使用 [get 笔记](https://www.biji.com/) API 进行知识抽取
- 使用 [markitdown](https://github.com/microsoft/markitdown) 进行格式转换
