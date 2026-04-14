# Davybase

> AI Native 知识生产线 - get 笔记 → Markdown → LLM 编译 → Obsidian Wiki

受 [Karpathy 的个人知识库 wiki 方案](https://karpathy.ai/llmcookbook/) 启发，Davybase 帮助你将被困在 get 笔记 APP 中的知识自动化导出，编译为带双向链接的结构化 wiki，最终发布到 Obsidian。

**v4.2 新特性**: Worker 池模式、Provider 级别限流控制、模型级进度追踪！

**v4.0 核心架构**: 并发管线、多 LLM 负载均衡、~76% 时间节省！

## 快速开始

### 方式 1: 并发 CLI (推荐 - v4.2)

```bash
# 并发抽取 (concurrency=3)
python main.py ingest --batch-size 20 --concurrency 3 --resume

# 并发消化 (Worker 池模式，自动限流控制)
python main.py digest --apply

# 并发编译 (2 批次并发，不同批次使用不同 LLM)
python main.py compile --kb-dir processed/编程+AI/ --concurrent-batches 2

# 一键执行全量管道
python main.py pipeline --full --resume
```

**Worker 池模式说明**:
- 3 个 Worker 同时处理（千问、智谱、MiniMax 各一个）
- 每个 Worker 独立领取任务，处理完立即领取下一批
- 自动限流控制：智谱 60s 间隔，千问/MiniMax 3s 间隔
- 实时进度追踪：显示每个模型的 ✓/✗ 计数

### 方式 2: AI Native (MCP + Skills)

```bash
# 1. 安装 MCP SDK
pip install --system mcp

# 2. 配置 MCP 服务器
# 编辑 ~/.claude/settings.json 添加:
{
  "mcpServers": {
    "davybase": {
      "command": "python",
      "args": ["/Users/qiming/workspace/davybase/src/mcp_server.py"]
    }
  }
}

# 3. 使用自然语言交互
/davybase status    # 查看管线状态
/davybase ingest    # 摄取笔记 (concurrency=3)
/davybase digest    # 消化处理 (concurrency=5, round_robin)
/davybase compile   # 编译 Wiki (concurrent_batches=2)
```

### 方式 3: 传统 CLI

```bash
# 安装依赖
pip install -r requirements.txt

# 配置凭据（首次使用）
/note config

# 全量同步
python main.py full-sync --provider zhipu

# 增量同步（日常使用）
python main.py incremental --provider zhipu

# 查看同步状态
python main.py status
```

## 功能特性

### v4.2 新增 (2026-04-14)

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
- **四阶段管线** - 摄取 → 消化 → 编译 → 发布，各司其职
- **多 LLM 支持** - 智谱 GLM5、千问 Qwen、MiniMax M2.7，可按需切换
- **智能编译** - LLM 识别核心概念，聚合多条笔记为结构化 wiki 条目
- **双链支持** - 自动生成 `[[双向链接]]` 和 frontmatter 标签
- **幂等安全** - 所有操作可重复执行，自动跳过已处理项
- **断点续传** - 支持从中断处恢复，不浪费 API 配额

## 架构图

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Extractor   |───>| Converter   |───>| Compiler    |───>| Writer      |
│ (get 笔记 API) |    │ (markitdown)│    │ (LLM)       │    │ (Obsidian)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      |                                                        |
      v                                                        v
 data/raw/                                              /ObsidianWiki/wiki/
 (原始笔记暂存)                                          (编译后的 wiki 条目)
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `full-sync [--provider zhipu\|minimax]` | 全量同步所有笔记 |
| `incremental [--provider zhipu\|minimax]` | 增量同步（新增/变更） |
| `extract-only` | 仅抽取，不编译（调试用） |
| `compile-only [--provider zhipu\|minimax]` | 重新编译已有的 raw/ |
| `status` | 查看同步状态 |
| `quota` | 检查 get 笔记 API 配额 |

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
data_path: ./data
logs_path: ./logs
```

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

## 相关笔记
- [[Transformer 模型]]
- [[注意力机制]]
```

自动生成的内容用 `%%davybase-auto-begin%%` / `%%davybase-auto-end%%` 包裹，重新同步时仅更新标记之间的内容，手动编辑会被保留。

## 定时同步

```bash
# 每天早上 6 点增量同步（crontab）
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py incremental >> logs/sync.log 2>&1
```

## 文档

- **[SECRETS_SETUP.md](docs/SECRETS_SETUP.md)** - 密钥配置指南（API 密钥获取和配置方法）
- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - 完整配置指南（config.yaml、CLI 参数）
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系统架构（四阶段管线、模块设计、数据库结构）
- **[USAGE.md](docs/USAGE.md)** - 使用指南（快速开始、常见工作流、故障排查）
- **[PIPELINE_CONFIG.md](docs/PIPELINE_CONFIG.md)** - 管线配置详细指南
- **[RATE_LIMIT_TROUBLESHOOTING.md](docs/RATE_LIMIT_TROUBLESHOOTING.md)** - 限流故障排查
- **[WORKER_POOL_IMPLEMENTATION.md](docs/WORKER_POOL_IMPLEMENTATION.md)** - Worker 池模式实施文档
- **[CONCURRENT_PIPELINE.md](docs/CONCURRENT_PIPELINE.md)** - 并发管线设计文档
- **[MCP_SERVER_GUIDE.md](docs/MCP_SERVER_GUIDE.md)** - MCP Server 配置指南
- **[CRON_SETUP.md](docs/CRON_SETUP.md)** - 定时任务配置指南

## 项目结构

```
davybase/
├── main.py                 # CLI 入口
├── config.yaml             # 配置文件
├── requirements.txt        # Python 依赖
├── src/
│   ├── extractor.py        # get 笔记 API 抽取
│   ├── converter.py        # markitdown 格式转换
│   ├── compiler.py         # LLM 编译
│   ├── writer.py           # Obsidian 写入
│   ├── sync_state.py       # SQLite 状态管理
│   ├── config.py           # 配置加载
│   ├── utils.py            # 工具函数
│   └── llm_providers/
│       ├── base.py         # LLMProvider 基类
│       ├── zhipu.py        # 智谱 GLM5
│       └── minimax.py      # MiniMax M2.7
├── data/
│   ├── raw/                # 原始笔记暂存区（.gitignore）
│   └── sync.db             # SQLite 数据库（.gitignore）
├── logs/                   # 日志文件（.gitignore）
├── tests/                  # 单元测试
└── docs/
    └── superpowers/
        ├── specs/          # 设计文档
        └── plans/          # 实现计划
```

## 依赖

- `httpx>=0.27` — 异步 HTTP 客户端
- `click>=8.0` — CLI 框架
- `pyyaml>=6.0` — YAML 配置解析
- `markitdown>=0.1.0` — Microsoft 格式转 Markdown 工具
- `sqlite3` — 标准库，状态跟踪

## 安全

- API 密钥配置在 `secrets.yaml` 文件中（已加入 `.gitignore`），或存储在环境变量中
- `.gitignore` 已配置排除敏感文件和数据
- 原始笔记数据不污染 Obsidian vault，只有编译后的 wiki 条目写入

## 开发

```bash
# 运行测试
pytest

# 运行特定测试
pytest tests/test_writer.py -v

# 查看测试覆盖
pytest --cov=src --cov-report=term-missing
```

## 许可证

MIT

## 致谢

- 灵感来自 [Andrej Karpathy 的个人知识库](https://karpathy.ai/llmcookbook/)
- 使用 [get 笔记](https://www.biji.com/) API 进行知识抽取
- 使用 [markitdown](https://github.com/microsoft/markitdown) 进行格式转换
