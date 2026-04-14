# Davybase 管线配置指南

**版本**: v4.1  
**创建日期**: 2026-04-14

---

## 概述

Davybase v4.1 将所有运行参数移至 `config.yaml` 配置文件，无需修改代码即可调整管线行为。

---

## 配置文件结构

```yaml
# config.yaml

# 并发管线配置（v4.0）
pipeline:
  # 阶段 1: 摄取（Ingest）- 从 get 笔记 API 抽取原始笔记
  ingest:
    enabled: true
    batch_size: 10          # 单批次最大抽取数量
    concurrency: 2          # 并发请求数（推荐 1-3，过高会触发 API 限流）
    rate_limit_delay: 2.0   # API 请求间隔（秒），触发限流时增加此值
    page_delay: 3.0         # 分页请求间隔（秒）
    resume: true            # 默认断点续传

  # 阶段 2: 消化（Digest）- 生成标题、分类、移动
  digest:
    enabled: true
    batch_size: 10          # 单批次处理数量
    concurrency: 3          # 并发任务数（推荐 1-5）
    provider_rotation: round_robin  # 多 LLM 分配策略
    apply: false            # 是否直接执行移动（预览模式=false）
    limit: null             # 限制处理数量（null=全部）

  # 阶段 3: 编译（Compile）- 聚合笔记为 Wiki 条目
  compile:
    enabled: true
    batch_size: 5           # 单批次笔记数量
    concurrent_batches: 1   # 同时编译的批次数量（推荐 1-2）
    provider_rotation: round_robin  # LLM 分配策略
    threshold: 3            # 触发编译的最小笔记数

# LLM 提供商配置
llm:
  default: qwen                         # 默认提供商
  rotation_order: [qwen, minimax, zhipu]  # 轮询顺序
  weights:                              # 加权策略权重
    qwen: 0.5
    minimax: 0.4
    zhipu: 0.1
```

---

## 参数详解

### 阶段 1: 摄取 (Ingest)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch_size` | int | 10 | 单批次最大抽取数量 |
| `concurrency` | int | 2 | 并发请求数，**推荐 1-3**，过高会触发 API 限流 |
| `rate_limit_delay` | float | 2.0 | API 请求间隔（秒），触发限流时增加此值 |
| `page_delay` | float | 3.0 | 分页请求间隔（秒） |
| `resume` | bool | true | 是否断点续传 |

**调优建议**:
- 频繁触发限流 → 降低 `concurrency` 至 1，增加 `rate_limit_delay` 至 3-5 秒
- 处理速度慢 → 增加 `batch_size` 至 15-20，`concurrency` 保持 2-3

### 阶段 2: 消化 (Digest)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `worker_mode` | string | batch | Worker 模式：`batch`（批次模式）\| `pool`（Worker 池模式） |
| `workers` | list | 见下方 | Worker 池模式配置（每个 Worker 独立领取任务） |
| `dynamic_batch` | object | 见下方 | 动态批次调整配置（根据处理速度自动调整） |
| `batch_size` | int | 10 | 单批次处理数量（批次模式使用） |
| `concurrency` | int | 3 | 并发任务数，**推荐 1-5**（批次模式使用） |
| `provider_rotation` | string | round_robin | LLM 分配策略：`single` \| `round_robin` \| `weighted` \| `dual`（批次模式使用） |
| `apply` | bool | false | 是否直接执行移动（false=预览模式） |
| `limit` | int/null | null | 限制处理数量（null=全部） |

**Worker 池模式配置 (worker_mode: pool)**:

```yaml
pipeline:
  digest:
    worker_mode: pool
    workers:
      - name: qwen
        provider: qwen
        batch_size: 2
      - name: zhipu
        provider: zhipu
        batch_size: 2
      - name: minimax
        provider: minimax
        batch_size: 2
```

**动态批次配置 (dynamic_batch)**:

```yaml
pipeline:
  digest:
    dynamic_batch:
      enabled: true             # 是否启用动态批次调整
      strategy: threshold       # threshold=阈值模式（稳健），aggressive=激进模式
      min_batch_size: 1         # 最小批次大小
      max_batch_size: 8         # 最大批次大小（避免触发限流）
      adjustment_window: 10     # 滑动窗口大小（最近 N 次处理）
      speed_threshold: 1.2      # 速度超过平均 20% 才增加批次
      rate_limit_decay: 0.5     # 限流时批次衰减系数（0.5=减半）
      cooldown_seconds: 30.0    # 批次调整冷却时间（秒）
```

**动态批次调整策略**:
- **threshold（推荐）**: 稳健模式，速度超过平均 20% 才增加批次，适合生产环境
- **aggressive**: 激进模式，速度快就增加，慢就减少，适合配额充足的场景

**限流场景下的行为**:
- 触发限流 → 批次立即减半（或减少 2，激进模式）
- 连续成功 → 根据速度逐步恢复批次
- 冷却时间 30 秒内不调整（避免频繁抖动）

**Worker 池模式特点**:
- 每个模型独立 Worker，真正的流水线作业
- 处理完立即领取下一批，无批次间等待
- 实时进度追踪，显示每个模型的 ✓/✗ 计数
- 动态批次调整，根据模型表现自动分配负载

### 阶段 3: 编译 (Compile)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch_size` | int | 5 | 单批次笔记数量 |
| `concurrent_batches` | int | 1 | 同时编译的批次数量，**推荐 1-2** |
| `provider_rotation` | string | round_robin | LLM 分配策略 |
| `threshold` | int | 3 | 触发编译的最小笔记数 |

**调优建议**:
- LLM 频繁失败 → 降低 `concurrent_batches` 至 1，减少并发压力
- 编译速度慢 → 增加 `concurrent_batches` 至 2，使用 `dual` 策略

---

## CLI 命令覆盖配置

CLI 命令的参数优先级高于配置文件。例如：

```bash
# 使用配置文件默认值
python main.py ingest

# 覆盖配置文件参数
python main.py ingest --batch-size 15 --concurrency 1

# 管道命令覆盖
python main.py pipeline --full \
  --ingest-batch-size 15 \
  --ingest-concurrency 1 \
  --digest-concurrency 5 \
  --compile-batch-size 10 \
  --compile-concurrent-batches 2
```

### Worker 池模式 CLI 示例

```bash
# 使用配置文件中的 Worker 池配置
python main.py digest --apply

# CLI 覆盖 Worker 模式
python main.py digest --worker-mode pool --apply

# CLI 覆盖 Worker 配置（JSON 字符串）
python main.py digest \
  --worker-mode pool \
  --workers '[{"name":"qwen","provider":"qwen","batch_size":2},{"name":"zhipu","provider":"zhipu","batch_size":2},{"name":"minimax","provider":"minimax","batch_size":2}]' \
  --limit 50 \
  --apply

# 回退到批次模式
python main.py digest --worker-mode batch --apply
```

---

## 限流问题解决方案

### get 笔记 API 限流

**症状**: 日志中出现「触发限流，等待 XX 秒」

**解决方案**:

1. **降低并发度**（最有效）:
   ```yaml
   pipeline:
     ingest:
       concurrency: 1  # 从 2 降至 1
   ```

2. **增加请求间隔**:
   ```yaml
   pipeline:
     ingest:
       rate_limit_delay: 3.0  # 从 2.0 增至 3-5 秒
       page_delay: 5.0        # 从 3.0 增至 5 秒
   ```

3. **减少批次大小**:
   ```yaml
   pipeline:
     ingest:
       batch_size: 5  # 从 10 降至 5
   ```

### LLM API 限流

**症状**: 日志中出现「429 Too Many Requests」或「配额不足」

**解决方案**:

1. **降低消化并发度**:
   ```yaml
   pipeline:
     digest:
       concurrency: 2  # 从 3 降至 2
   ```

2. **使用多 LLM 轮询**:
   ```yaml
   pipeline:
     digest:
       provider_rotation: dual  # 或 round_robin
   ```

3. **降低编译并发批次数**:
   ```yaml
   pipeline:
     compile:
       concurrent_batches: 1  # 从 2 降至 1
   ```

---

## 推荐配置模板

### 保守配置（稳定优先，适合 API 配额有限）

```yaml
pipeline:
  ingest:
    batch_size: 5
    concurrency: 1          # 单并发，最稳定
    rate_limit_delay: 3.0
    page_delay: 5.0

  digest:
    batch_size: 5
    concurrency: 2
    provider_rotation: dual

  compile:
    batch_size: 3
    concurrent_batches: 1   # 单批次编译
```

### 平衡配置（推荐默认）

```yaml
pipeline:
  ingest:
    batch_size: 10
    concurrency: 2
    rate_limit_delay: 2.0
    page_delay: 3.0

  digest:
    batch_size: 10
    concurrency: 3
    provider_rotation: round_robin

  compile:
    batch_size: 5
    concurrent_batches: 1
```

### 激进配置（速度快，但可能触发限流）

```yaml
pipeline:
  ingest:
    batch_size: 15
    concurrency: 3          # 高并发
    rate_limit_delay: 1.5

  digest:
    batch_size: 15
    concurrency: 5
    provider_rotation: dual

  compile:
    batch_size: 10
    concurrent_batches: 2   # 双批次并发
```

---

## 故障排查

### 问题：抽取笔记频繁失败

**检查清单**:
- [ ] `concurrency` 是否过高（建议 1-2）
- [ ] `rate_limit_delay` 是否过短（建议 2-3 秒）
- [ ] API 密钥是否正确

### 问题：消化速度慢

**优化建议**:
- [ ] 增加 `concurrency` 至 5
- [ ] 使用 `dual` 或 `round_robin` 策略
- [ ] 确保多个 LLM 都有充足配额

### 问题：编译生成 0 个条目

**检查清单**:
- [ ] 笔记数量是否达到 `threshold`
- [ ] `batch_size` 配置是否过小
- [ ] LLM API 密钥是否正确

---

## 参考文档

- [CONFIGURATION.md](CONFIGURATION.md) - 完整配置指南
- [CONCURRENT_PIPELINE.md](CONCURRENT_PIPELINE.md) - 并发管线设计文档
- [SECRETS_SETUP.md](SECRETS_SETUP.md) - API 密钥配置
