# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
