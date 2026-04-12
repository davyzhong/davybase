# Davybase 配置指南

本文档说明 Davybase 的所有配置项和配置方法。

## 配置概览

Davybase 的配置分为三层：

```
┌─────────────────────────────────────────────────────────┐
│  环境变量（敏感凭据）                                     │
│  - GETNOTE_API_KEY                                      │
│  - GETNOTE_CLIENT_ID                                    │
│  - ZHIPU_API_KEY / MINIMAX_API_KEY                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  config.yaml（应用配置）                                  │
│  - vault_path                                           │
│  - data_path                                            │
│  - compiler 配置                                         │
│  - sync 配置                                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  运行时配置（命令行参数）                                  │
│  - --provider                                           │
│  - --batch-size                                         │
│  - --resume                                             │
└─────────────────────────────────────────────────────────┘
```

---

## 1. 环境变量（敏感凭据）

所有 API 密钥等敏感信息通过环境变量配置，**永不写入源代码或配置文件**。

### 1.1 get 笔记 API 凭据

| 变量名 | 说明 | 格式示例 | 获取方式 |
|--------|------|----------|----------|
| `GETNOTE_API_KEY` | get 笔记 API 密钥 | `gk_live_xxx` | 运行 `/note config` |
| `GETNOTE_CLIENT_ID` | get 笔记 Client ID | `cli_xxx` | 运行 `/note config` |

**配置方法：**

```bash
# 方法 1：使用 getnote Skill（推荐）
/note config

# 方法 2：手动设置环境变量
export GETNOTE_API_KEY=gk_live_xxxxxxxxxxxxx
export GETNOTE_CLIENT_ID=cli_xxxxxxxxxxxxx
```

### 1.2 LLM API 密钥

| 变量名 | 说明 | 格式示例 | 获取方式 |
|--------|------|----------|----------|
| `ZHIPU_API_KEY` | 智谱 AI API 密钥 | `xxxxxxxx.xxxxxxxxx` | [智谱 AI 开放平台](https://open.bigmodel.cn/) |
| `MINIMAX_API_KEY` | MiniMax API 密钥 | `xxxxxxxxxxxxx` | [MiniMax 开放平台](https://platform.minimaxi.com/) |

**配置方法：**

```bash
# 添加到 ~/.zshrc（永久生效）
echo 'export ZHIPU_API_KEY=your_zhipu_api_key' >> ~/.zshrc
echo 'export MINIMAX_API_KEY=your_minimax_api_key' >> ~/.zshrc
source ~/.zshrc

# 或临时设置（当前终端会话）
export ZHIPU_API_KEY=your_zhipu_api_key
export MINIMAX_API_KEY=your_minimax_api_key
```

### 1.3 验证配置

```bash
# 检查环境变量是否设置
echo $GETNOTE_API_KEY
echo $ZHIPU_API_KEY
echo $MINIMAX_API_KEY

# 运行 Davybase 检查配置
python main.py status
```

---

## 2. config.yaml（应用配置）

`config.yaml` 位于项目根目录，控制 Davybase 的运行行为。

### 2.1 完整配置示例

```yaml
# Davybase 配置文件
# 敏感信息（API 密钥）存放在环境变量中

# ============= 路径配置 =============
vault_path: /Users/qiming/ObsidianWiki    # Obsidian Vault 路径
data_path: /Users/qiming/ObsidianWiki/raw  # 原始笔记存储路径
logs_path: /Users/qiming/ObsidianWiki/logs # 日志文件路径

# ============= 编译器配置 =============
compiler:
  default_provider: zhipu           # 默认 LLM 提供商：zhipu 或 minimax
  batch_size: 15                    # 单批次最大笔记数
  max_retries: 2                    # LLM 调用最大重试次数
  
  # LLM 提供商配置
  providers:
    zhipu:
      model: glm-5                  # 智谱模型版本
      name: 智谱 GLM5
    minimax:
      model: codex-MiniMax-M2.7     # MiniMax 模型版本
      name: MiniMax M2.7

# ============= 同步配置 =============
sync:
  schedule: "0 6 * * *"             # cron 表达式，每天早上 6 点
  rate_limit_delay: 1.0             # API 请求间隔（秒）
```

### 2.2 配置项说明

#### 路径配置

| 配置项 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `vault_path` | Obsidian Vault 根目录 | - | 是 |
| `data_path` | 原始笔记存储目录 | `./data` | 否 |
| `logs_path` | 日志文件目录 | `./logs` | 否 |

#### 编译器配置

| 配置项 | 说明 | 默认值 | 推荐值 |
|--------|------|--------|--------|
| `compiler.default_provider` | 默认 LLM 提供商 | `zhipu` | `zhipu` |
| `compiler.batch_size` | 单批次处理笔记数 | `15` | `10-20` |
| `compiler.max_retries` | LLM 调用重试次数 | `2` | `2-3` |

#### 同步配置

| 配置项 | 说明 | 默认值 | 说明 |
|--------|------|--------|------|
| `sync.schedule` | 定时同步计划 | `0 6 * * *` | cron 表达式 |
| `sync.rate_limit_delay` | API 请求间隔 | `1.0` | 避免触发限流 |

---

## 3. 运行时配置（命令行参数）

通过命令行参数覆盖配置文件中的设置。

### 3.1 全局参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--provider <name>` | 指定 LLM 提供商 | config.yaml 中的 `default_provider` |
| `--batch-size <N>` | 单批次处理数 | config.yaml 中的 `batch_size` |
| `--resume` | 从中断处恢复 | `false` |
| `--dry-run` | 预览模式，不实际写入 | `false` |
| `--verbose` | 详细日志输出 | `false` |

### 3.2 命令示例

```bash
# 使用 MiniMax 进行全量同步
python main.py full-sync --provider minimax

# 增量同步，批处理大小 50
python main.py incremental --batch-size 50

# 预览模式（不实际写入）
python main.py full-sync --dry-run

# 从中断处恢复
python main.py incremental --resume
```

---

## 4. 故障排查

### 4.1 配置问题诊断

```bash
# 检查配置加载
python -c "from src.config import load_config; print(load_config())"

# 检查环境变量
env | grep -E 'GETNOTE|ZHIPU|MINIMAX'

# 测试 API 连接
python main.py quota
```

### 4.2 常见问题

#### 问题 1：找不到配置文件

```
错误：config.yaml not found
```

**解决：** 确保在项目根目录运行，或复制 `config.example.yaml` 为 `config.yaml`

#### 问题 2：API 密钥未设置

```
错误：GETNOTE_API_KEY not set
```

**解决：** 运行 `/note config` 或手动设置环境变量

#### 问题 3：Obsidian Vault 路径不存在

```
错误：vault_path does not exist: /path/to/vault
```

**解决：** 检查 `config.yaml` 中的 `vault_path` 是否正确，确保 Obsidian 已打开该 Vault

---

## 5. 配置文件版本

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-04-11 | 初始版本 |
| 1.1 | 2026-04-12 | 新增 note-summarizer Skill 配置 |

---

## 6. 相关文档

- [README.md](../README.md) - 项目概述和快速开始
- [USAGE.md](USAGE.md) - 详细使用指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构说明
