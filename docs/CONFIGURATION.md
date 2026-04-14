# Davybase 配置指南

**版本**: v4.2  
**更新日期**: 2026-04-14

本文档说明 Davybase 的配置方法。

## 配置分层

Davybase 的配置分为两层：

```
┌─────────────────────────────────────────────────────────┐
│  密钥配置（API 密钥等敏感凭据）                           │
│  - 方式 1：secrets.yaml 文件（推荐）                     │
│  - 方式 2：环境变量（优先级更高）                        │
│  详见：docs/SECRETS_SETUP.md                            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  config.yaml（应用配置）                                  │
│  - vault_path, data_path, logs_path                     │
│  - compiler 配置                                         │
│  - pipeline 配置（并发管线 v4.0）                        │
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

## 1. 密钥配置（API 密钥）

**重要：** API 密钥等敏感信息请配置 `secrets.yaml` 文件或使用环境变量。

**详见 [docs/SECRETS_SETUP.md](SECRETS_SETUP.md)** - 包含详细的密钥获取和配置步骤。

### 方式一：secrets.yaml 文件（推荐）

```bash
# 复制示例文件
cp secrets.example.yaml secrets.yaml

# 编辑 secrets.yaml，填入你的 API 密钥
# 设置文件权限
chmod 600 secrets.yaml
```

### 方式二：环境变量（优先级更高）

```bash
# get 笔记
export GETNOTE_API_KEY=gk_live_xxx
export GETNOTE_CLIENT_ID=cli_xxx

# 智谱
export ZHIPU_API_KEY=your_zhipu_api_key

# MiniMax
export MINIMAX_API_KEY=your_minimax_api_key
```

**优先级说明：** 如果同时配置了 `secrets.yaml` 和环境变量，环境变量会覆盖 `secrets.yaml` 中的值。

---

## 2. config.yaml（应用配置）

`config.yaml` 位于项目根目录，控制 Davybase 的运行行为。

### 2.1 完整配置示例

```yaml
# Davybase 配置文件
# 敏感信息（API 密钥）配置：
# 方式 1（推荐）：复制 secrets.example.yaml 为 secrets.yaml 并填入密钥
# 方式 2：设置环境变量（GETNOTE_API_KEY, ZHIPU_API_KEY 等）
# 详见：docs/SECRETS_SETUP.md

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

#### 问题 1：找不到密钥配置

```
错误：未配置 API 密钥
```

**解决：** 
- 复制 `secrets.example.yaml` 为 `secrets.yaml` 并填入密钥
- 或设置相应的环境变量

#### 问题 2：Obsidian Vault 路径不存在

```
错误：vault_path does not exist: /path/to/vault
```

**解决：** 检查 `config.yaml` 中的 `vault_path` 是否正确，确保 Obsidian 已打开该 Vault

---

## 5. pipeline 并发管线配置 (v4.0/v4.2)

`config.yaml` 中的 `pipeline` 配置控制并发管线行为。

### 5.1 完整配置示例

```yaml
pipeline:
  # 阶段 1: 摄取（Ingest）- 从 get 笔记 API 抽取原始笔记
  ingest:
    enabled: true
    batch_size: 10          # 单批次最大抽取数量
    concurrency: 2          # 并发请求数（推荐 1-3，过高会触发 API 限流）
    rate_limit_delay: 2.0   # API 请求间隔（秒）
    page_delay: 3.0         # 分页请求间隔（秒）
    resume: true            # 默认断点续传

  # 阶段 2: 消化（Digest）- 生成标题、分类、移动
  digest:
    enabled: true
    worker_mode: pool           # pool=Worker 池模式，batch=批次模式
    workers:                    # Worker 池模式配置（每个 Worker 独立领取任务）
      - name: qwen
        provider: qwen
        batch_size: 2
      - name: zhipu
        provider: zhipu
        batch_size: 1           # 智谱 TPM 配额低，降至 1
      - name: minimax
        provider: minimax
        batch_size: 2
    
    # Provider 级别请求间隔配置（秒）
    provider_rate_limit_delays:
      zhipu: 60.0      # 智谱 TPM 配额低，需 60 秒间隔
      qwen: 3.0        # 千问配额充足，3 秒足够
      minimax: 3.0     # MiniMax 配额充足，3 秒足够
    
    batch_size: 10          # 批次模式使用
    concurrency: 3          # 批次模式使用
    provider_rotation: weighted  # 加权轮询
    apply: false            # 预览模式=false
    limit: null             # null=全部

  # 阶段 3: 编译（Compile）- 聚合笔记为 Wiki 条目
  compile:
    enabled: true
    batch_size: 5           # 单批次笔记数量
    concurrent_batches: 1   # 同时编译的批次数量（推荐 1-2）
    provider_rotation: round_robin
    threshold: 3            # 触发编译的最小笔记数
```

### 5.2 Provider 级别限流控制 (v4.2)

**背景**: 不同 LLM API 的 TPM（Tokens Per Minute）配额差异很大，需要独立配置请求间隔。

| Provider | 推荐间隔 | 理由 |
|----------|---------|------|
| zhipu | 60.0s | TPM 配额约 100-200 tokens/分钟，每次 digest 约 100 tokens |
| qwen | 3.0s | 配额充足，3 秒足够恢复 |
| minimax | 3.0s | 配额充足，3 秒足够恢复 |

**配置方法**:
```yaml
digest:
  provider_rate_limit_delays:
    zhipu: 60.0
    qwen: 3.0
    minimax: 3.0
```

### 5.3 Worker 池模式配置 (v4.2)

**worker_mode: pool** - 真正的流水线作业，每个模型独立 Worker：

```yaml
digest:
  worker_mode: pool
  workers:
    - name: qwen
      provider: qwen
      batch_size: 2       # 每次处理 2 条
    - name: zhipu
      provider: zhipu
      batch_size: 1       # 智谱配额低，降至 1
    - name: minimax
      provider: minimax
      batch_size: 2
```

**worker_mode: batch** - 批次模式（v4.0 默认）：

```yaml
digest:
  worker_mode: batch
  batch_size: 10
  concurrency: 3
  provider_rotation: round_robin
```

### 5.4 参数说明

#### Ingest 阶段

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch_size` | int | 10 | 单批次最大抽取数量 |
| `concurrency` | int | 2 | 并发请求数，**推荐 1-3** |
| `rate_limit_delay` | float | 2.0 | API 请求间隔（秒） |
| `page_delay` | float | 3.0 | 分页请求间隔（秒） |
| `resume` | bool | true | 断点续传 |

#### Digest 阶段

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `worker_mode` | string | pool | `pool`=Worker 池模式，`batch`=批次模式 |
| `workers` | list | 见上 | Worker 池模式配置 |
| `provider_rate_limit_delays` | object | 见上 | Provider 级别请求间隔 |
| `batch_size` | int | 10 | 批次模式使用 |
| `concurrency` | int | 3 | 批次模式使用 |
| `provider_rotation` | string | weighted | `single`/`round_robin`/`weighted`/`dual` |
| `apply` | bool | false | 直接执行移动 |
| `limit` | int/null | null | 限制处理数量 |

#### Compile 阶段

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch_size` | int | 5 | 单批次笔记数量 |
| `concurrent_batches` | int | 1 | 同时编译的批次数量 |
| `provider_rotation` | string | round_robin | LLM 分配策略 |
| `threshold` | int | 3 | 触发编译的最小笔记数 |

---

## 6. 配置文件版本

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-04-11 | 初始版本 |
| 2.0 | 2026-04-12 | 引入 secrets.yaml 集中管理密钥 |
| 4.0 | 2026-04-13 | 新增 pipeline 并发管线配置 |
| 4.2 | 2026-04-14 | 新增 provider_rate_limit_delays 和 Worker 池模式 |

---

## 7. 相关文档

- [README.md](../README.md) - 项目概述和快速开始
- [SECRETS_SETUP.md](SECRETS_SETUP.md) - 密钥配置详细指南
- [USAGE.md](USAGE.md) - 详细使用指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构说明
- [PIPELINE_CONFIG.md](PIPELINE_CONFIG.md) - 管线配置详细指南
- [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md) - 限流故障排查
