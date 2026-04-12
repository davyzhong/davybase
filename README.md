# Davybase

> get 笔记 → Markdown → LLM 编译 → Obsidian Wiki 的知识库管线

受 [Karpathy 的个人知识库 wiki 方案](https://karpathy.ai/llmcookbook/) 启发，Davybase 帮助你将被困在 get 笔记 APP 中的知识自动化导出，编译为带双向链接的结构化 wiki，最终发布到 Obsidian。

## 快速开始

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

- **四阶段管线**：Extractor → Converter → Compiler → Writer，各司其职
- **多 LLM 支持**：智谱 GLM5、MiniMax M2.7，可按需切换
- **智能编译**：LLM 识别核心概念，聚合多条笔记为结构化 wiki 条目
- **双链支持**：自动生成 `[[双向链接]]` 和 frontmatter 标签
- **冲突处理**：保留手动编辑内容，仅更新自动生成的摘要块
- **增量同步**：SQLite 跟踪同步状态，仅处理新增/变更的笔记
- **速率限制**：自动处理 API 限流，指数退避重试

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
