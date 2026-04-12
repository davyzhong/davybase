# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ 重要：项目原则文件

**每次执行操作前必须阅读**：在编写代码、修改功能或执行任何批量操作之前，必须先阅读项目原则文件：

```bash
# 必读文件
cat rules/principles.md
cat rules/knowledge-base-structure.md
```

**核心原则**：
1. **幂等性原则** - 所有操作前必须检查是否已执行过，避免重复处理
2. **知识库结构约束** - 目录层级最多两级，一级目录 ≤ 20 个，二级目录 ≤ 10 个
3. **状态追踪** - 批量操作必须有状态记录和断点续传支持

详见 [`rules/principles.md`](rules/principles.md) 和 [`rules/knowledge-base-structure.md`](rules/knowledge-base-structure.md)。

---

## 项目初始化 / Code Review 检查清单

**每次项目初始化或 Code Review 时，必须执行以下步骤：**

1. **阅读原则文件** - 重温项目设计原则
   - [ ] 已阅读 `rules/principles.md`
   - [ ] 已阅读 `rules/knowledge-base-structure.md`

2. **检查幂等性** - 代码是否遵守避免重复操作原则
   - [ ] 操作前有状态检查（如 `is_summarized()`, `is_classified()`）
   - [ ] 支持断点续传和中断恢复
   - [ ] 日志中显示"跳过已处理"的提示

3. **检查知识库结构约束** - 目录创建是否符合约束
   - [ ] 一级目录数量 ≤ 20
   - [ ] 二级目录数量 ≤ 10
   - [ ] 目录层级最多两级

4. **检查状态标识** - 处理后是否添加标识
   - [ ] Frontmatter 中添加 `summarized`, `classified`, `moved_to_kb` 等字段
   - [ ] 进度文件 `.processing_status.json` 更新

---

## Project Overview

Davybase - get 笔记到 Obsidian Wiki 的知识库管线

**GitHub Repository:** https://github.com/davyzhong/davybase

## Quick Start

```bash
# 全量同步
python main.py full-sync --provider zhipu|minimax

# 增量同步
python main.py incremental --provider zhipu|minimax

# 查看状态
python main.py status

# 使用 Obsidian CLI 模式（默认）
python main.py full-sync --provider zhipu

# 强制使用文件系统模式
python main.py full-sync --provider zhipu --no-cli
```

## Configuration

1. **get 笔记 API 凭据** - 环境变量：
   - `GETNOTE_API_KEY` - 运行 `/note config` 配置
   - `GETNOTE_CLIENT_ID` - 运行 `/note config` 配置

2. **LLM API 密钥** - 环境变量：
   - `ZHIPU_API_KEY` - 智谱 GLM5
   - `MINIMAX_API_KEY` - MiniMax M2.7

## Git Workflow

**每次完成变动和更改后，必须执行以下步骤：**

1. **更新项目文档** - 确保 README.md 或其他文档反映最新变更
2. **提交更改** - 使用描述性的提交消息
3. **推送到远程** - `git push`

```bash
# 示例工作流
git add -A
git commit -m "feat: 描述你的更改"
git push
```

**不要提交的文件：**
- `data/raw/` - 原始笔记暂存区
- `data/_failed/` - 失败项目暂存区
- `data/sync.db` - SQLite 数据库
- `logs/` - 日志文件
- `wiki/` - Obsidian Wiki 输出目录
- 任何密钥、API Key、`.env` 文件

**重要：** 知识库的 Markdown 文件（从 get 笔记转换而来的内容）不应该提交到 GitHub。

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Extractor   |───>| Converter   |───>| Compiler    |───>| Writer      |
│ (get 笔记 API) |    │ (markitdown)│    │ (LLM)       │    │ (Obsidian)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Testing

```bash
# 运行所有测试
python -m pytest

# 运行特定测试
python -m pytest tests/test_writer.py -v
```

## Key Files

- `main.py` - CLI 入口
- `src/extractor.py` - get 笔记 API 抽取
- `src/converter.py` - markitdown 格式转换
- `src/compiler.py` - LLM 编译
- `src/writer.py` - Obsidian 写入（支持 CLI 和文件系统模式）
- `src/llm_providers/` - LLM 提供商（zhipu、minimax）
- `config.yaml` - 配置文件
