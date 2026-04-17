# Davybase 使用指南

**版本**: v5.0  
**更新日期**: 2026-04-17

详细的 Davybase 使用说明和常见工作流。

---

## 📌 重要：首次使用必读

Davybase 采用 **"一次性全量 + 每日增量"** 工作流：

| 步骤 | 操作 | 频率 | 说明 |
|------|------|------|------|
| **第 1 步** | 全量同步 | **仅一次** | 首次使用时处理所有历史笔记 |
| **第 2 步** | 增量同步 | **每日自动** | 仅处理新增/修改的笔记 |

**新手指引**: 详细说明见 [INITIALIZATION.md](INITIALIZATION.md)

### 快速开始流程

```bash
# 第 1 步：首次全量同步（仅执行一次）
python main.py pipeline --full --resume

# 第 2 步：设置每日自动增量同步（crontab）
crontab -e
# 添加：0 6 * * * cd /path/to/davybase && python main.py incremental
```

---

## 快速开始

### 1. 配置环境

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入你的 API 密钥
# - get 笔记 API 凭据：运行 /note config 获取
# - LLM API 密钥：从智谱 AI、千问或 MiniMax 平台获取
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 验证配置

```bash
# 检查配置是否加载成功
python main.py status

# 测试 LLM 配额
python main.py quota
```

### 4. 运行全量管道（推荐）

```bash
# 使用并发管线进行全量同步
python main.py pipeline --full --resume
```

**或者分阶段执行**:

```bash
# 阶段 1: 并发抽取
python main.py ingest --batch-size 20 --concurrency 3 --resume

# 阶段 2: 并发消化（Worker 池模式）
python main.py digest --apply

# 阶段 3: 并发编译
python main.py compile --kb-dir processed/ --concurrent-batches 2
```

---

## 常见工作流

### v5.0 两条 Skills 工作流（推荐）

**前半段：get 笔记整理助手（每日自动）**:

```bash
# 每日增量同步（建议设置定时任务自动执行）
python main.py incremental

# 或者使用 Skills
/getnote-organizer
```

**后半段：Wiki 知识创作助手（按需执行）**：

```bash
# 当某个主题积累 10+ 条笔记时执行
python main.py compile --kb-dir processed/ --concurrent-batches 2

# 或者使用 Skills
/wiki-creator
```

### v4.2 并发管线工作流

**全量管道**:
```bash
python main.py pipeline --full --resume
```

**分阶段执行**:

```bash
# 阶段 1: 并发抽取（100 条笔记约 2-3 分钟）
python main.py ingest --batch-size 20 --concurrency 2 --resume

# 阶段 2: 并发消化（Worker 池模式，50 条笔记约 5-8 分钟）
python main.py digest --apply

# 阶段 3: 并发编译（20 个 Wiki 条目约 3-5 分钟）
python main.py compile --kb-dir processed/ --concurrent-batches 2
```

### 传统工作流（v3.0，仍可用）

#### 全量同步 (Full Sync)

首次使用或需要完全重建 Wiki 时使用：

```bash
python main.py full-sync --provider zhipu
```

**过程说明：**
1. Extractor 从 get 笔记 API 获取所有笔记
2. Converter 格式化笔记为标准 Markdown
3. Compiler 调用 LLM 编译笔记为 Wiki 条目
4. Writer 写入 Obsidian Vault

**预计耗时：** 取决于笔记数量，约 10-30 分钟

#### 增量同步 (Incremental Sync)

日常使用，仅同步新增或修改的笔记：

```bash
python main.py incremental
```

**特点：**
- 自动检测新增/修改的笔记
- 跳过未变化的笔记
- 支持断点续传

**从中断处恢复：**
```bash
python main.py incremental --resume
```

#### 仅编译模式

如果已有原始笔记，仅需 LLM 编译：

```bash
python main.py compile-only --provider zhipu
```

#### 预览模式

测试配置，不实际写入文件：

```bash
python main.py full-sync --dry-run
```

---

## 命令行参数

### v4.2 并发管线命令

| 命令 | 说明 | 主要参数 |
|------|------|---------|
| `ingest` | 并发抽取笔记 | `--batch-size`, `--concurrency`, `--resume` |
| `digest` | 并发消化笔记 | `--apply`, `--limit`, `--worker-mode` |
| `compile` | 并发编译 Wiki | `--kb-dir`, `--concurrent-batches` |
| `pipeline` | 一键全量管道 | `--full`, `--resume` |

### 命令示例

```bash
# 并发抽取（推荐配置）
python main.py ingest --batch-size 20 --concurrency 2 --resume

# 并发消化（Worker 池模式）
python main.py digest --apply

# 并发消化（限制处理 50 条测试）
python main.py digest --limit 50 --apply

# 并发编译（2 批次并发）
python main.py compile --kb-dir processed/编程+AI/ --concurrent-batches 2

# 全量管道
python main.py pipeline --full --resume
```

### 传统命令（仍可用）

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--provider <name>` | LLM 提供商 (zhipu/minimax/qwen) | config.yaml 中的 default_provider |
| `--batch-size <N>` | 单批次处理笔记数 | 15 |
| `--resume` | 从中断处恢复 | false |
| `--dry-run` | 预览模式，不实际写入 | false |
| `--verbose` | 详细日志输出 | false |

### 命令示例

```bash
# 使用 MiniMax，批处理大小 50
python main.py full-sync --provider minimax --batch-size 50

# 增量同步，详细日志
python main.py incremental --verbose

# 预览模式
python main.py compile-only --dry-run

# 从中断处恢复
python main.py incremental --resume
```

---

## 故障排查

### v4.2 限流故障

**详细排查指南**: 见 [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md)

**快速诊断**:

```bash
# 查看限流日志
grep "触发限流" logs/*.log

# 查看模型级统计
grep "模型级统计" logs/digest.log -A 10
```

**智谱 API 限流解决方案**:
```yaml
# config.yaml
pipeline:
  digest:
    workers:
      - name: zhipu
        batch_size: 1       # 降至 1
    provider_rate_limit_delays:
      zhipu: 60.0           # 增至 60 秒

llm:
  weights:
    zhipu: 0.05             # 降至 5%
```

### 常见问题

#### 1. API Key 未设置

```
错误：GETNOTE_API_KEY not set
```

**解决：**
```bash
# 运行 getnote Skill 配置
/note config

# 或手动设置环境变量
export GETNOTE_API_KEY=gk_live_xxx
export GETNOTE_CLIENT_ID=cli_xxx
```

#### 2. LLM 配额不足

```
错误：API quota exceeded
```

**解决：**
- 检查 LLM 平台配额余额
- 切换到备用提供商：`--provider minimax`
- 充值 API 配额

#### 3. Obsidian Vault 路径不存在

```
错误：vault_path does not exist
```

**解决：**
- 检查 `config.yaml` 中的 `vault_path` 配置
- 确保 Obsidian 已打开该 Vault

#### 4. 同步中断后恢复

```bash
# 使用 --resume 参数继续
python main.py incremental --resume
```

### 日志位置

日志文件位于 `logs/` 目录（需在 `config.yaml` 中配置）：

```bash
# 查看最新日志
tail -f logs/davybase.log

# 查看错误日志
grep ERROR logs/davybase.log
```

---

## 最佳实践

### 1. 首次同步（仅执行一次）

**重要**: 首次使用 Davybase 时，先执行全量同步建立基线。

```bash
# 全量同步（一次性）
python main.py pipeline --full --resume
```

### 2. 日常同步（每日自动）

**设置定时任务**:

```bash
# crontab 配置（每天早上 6 点自动执行）
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py incremental >> logs/incremental.log 2>&1
```

**监控同步状态**:

```bash
# 每天早上 6 点自动同步
0 6 * * * cd /path/to/davybase && python main.py incremental
```

### 3. 批处理大小调整

根据 API 限流情况调整：

- 默认 `batch_size: 15`
- 如果频繁触发限流，降低到 `5-10`
- 如果配额充足，可提高到 `30-50`

### 4. 多提供商降级

配置自动降级策略：

```yaml
compiler:
  default_provider: zhipu
  # 如果 zhipu 失败，自动切换到 minimax
```

---

## FAQ

### Q: 全量同步和增量同步有什么区别？

**A:** 
- **全量同步**：处理所有笔记，**仅首次使用时执行一次**
- **增量同步**：仅处理新增/修改的笔记，**每日自动执行**

**工作流**:
```
第 1 次使用 → python main.py pipeline --full --resume（一次性）
每日使用  → python main.py incremental（定时任务自动执行）
```

### Q: 如何知道是增量同步还是全量同步？

**A**: 查看命令行输出或日志：
- 增量同步会显示"跳过 XXX 条已处理笔记"
- 全量同步会处理所有笔记

运行 `python main.py status` 查看上次同步类型：
```bash
python main.py status
# 输出示例：
# 上次同步：2026-04-17T06:00:00 (incremental, qwen)
#                                    ↑ 这里显示同步类型
```

### Q: 我不小心执行了两次全量同步，会有问题吗？

**A**: 不会有数据问题，系统使用 `content_hash` 比对，重复内容不会被重复处理。但会浪费时间和 API 配额。

### Q: 如何知道同步是否完成？

**A**:
- 运行 `python main.py status` 查看同步状态

### Q: 同步过程中可以中断吗？

**A:** 
可以。使用 `--resume` 参数从中断处继续：
```bash
python main.py incremental --resume
```

### Q: 如何清空同步状态重新同步？

**A:** 
删除 SQLite 数据库文件：
```bash
rm data/sync.db
python main.py full-sync
```

### Q: 支持哪些 LLM 提供商？

**A:** 
目前支持：
- **智谱 GLM5** (`zhipu`) - 通用场景，但 TPM 配额低（需 60s 间隔）
- **千问 Qwen** (`qwen`) - 中文理解好，配额充足（推荐主力）
- **MiniMax M2.7** (`minimax`) - 代码理解好，配额充足（推荐主力）

### Q: Worker 池模式 vs 批次模式有什么区别？

**A:**
- **Worker 池模式** (v4.2 推荐): 每个模型独立 Worker，处理完立即领取下一批，真正的流水线作业
- **批次模式** (v4.0): 预先分批次，批次间等待，非真正流水线

**推荐配置**:
```yaml
digest:
  worker_mode: pool  # Worker 池模式
```

### Q: 智谱 API 频繁触发限流怎么办？

**A:** 
这是智谱 GLM-5 TPM 配额极低（~100-200 tokens/分钟）导致的。解决方案：

1. **降低批次大小**: `batch_size: 1`
2. **增加延迟**: `provider_rate_limit_delays.zhipu: 60.0`
3. **降低权重**: `llm.weights.zhipu: 0.05`
4. **使用加权轮询**: `provider_rotation: weighted`

详见 [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md)

---

## 相关文档

- [README.md](../README.md) - 项目概述和快速开始
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构说明
- [PIPELINE_CONFIG.md](PIPELINE_CONFIG.md) - 管线配置详细指南
- [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md) - 限流故障排查
- [WORKER_POOL_IMPLEMENTATION.md](WORKER_POOL_IMPLEMENTATION.md) - Worker 池模式实施文档
