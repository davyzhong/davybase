# 限流故障排查指南

**版本**: v4.2  
**创建日期**: 2026-04-14

---

## 执行摘要

本文档提供 Davybase v4.2 的限流故障排查指南，覆盖：
1. **get 笔记 API 限流** - RPM（Requests Per Minute）限制
2. **LLM API 限流** - TPM（Tokens Per Minute）限制
3. **智谱 API 严重限流** - TPM 配额极低场景的专项解决方案

---

## 限流类型诊断

### 1. get 笔记 API 限流（RPM 限制）

**症状**:
```
WARNING davybase.extractor get 笔记 API 触发限流，等待 30 秒
```

**根本原因**:
- 并发请求数过高（concurrency > 3）
- 请求间隔过短（rate_limit_delay < 2s）
- 分页请求过频（page_delay < 3s）

**解决方案**:

| 措施 | 配置修改 | 效果 |
|------|---------|------|
| 降低并发度 | `ingest.concurrency: 1` | 最稳定，100% 避免限流 |
| 增加请求间隔 | `ingest.rate_limit_delay: 3.0-5.0` | 减少 RPM 压力 |
| 减少批次大小 | `ingest.batch_size: 5` | 减少单批次请求数 |

**推荐配置组合**:
```yaml
pipeline:
  ingest:
    batch_size: 5           # 从 10 降至 5
    concurrency: 1          # 从 2 降至 1
    rate_limit_delay: 3.0   # 从 2.0 增至 3.0
    page_delay: 5.0         # 从 3.0 增至 5.0
```

---

### 2. LLM API 限流（TPM 限制）

**症状**:
```
WARNING davybase.llm XX API 触发限流，等待 30 秒（第 1/5 次重试）
```

**根本原因**:
- 并发任务数过高（digest.concurrency > 5）
- 单一 LLM 配额耗尽
- 批次大小过大（batch_size > 2）

**通用解决方案**:

| 措施 | 配置修改 | 效果 |
|------|---------|------|
| 降低消化并发 | `digest.concurrency: 2-3` | 减少并发压力 |
| 多 LLM 轮询 | `digest.provider_rotation: round_robin` | 分散限流风险 |
| 降低批次大小 | `digest.batch_size: 2-3` | 减少单次 TPM 消耗 |

**推荐配置组合**:
```yaml
pipeline:
  digest:
    batch_size: 2
    concurrency: 3
    provider_rotation: round_robin
```

---

### 3. 智谱 API 严重限流（TPM 配额极低）

**症状**:
```
WARNING davybase.llm 智谱 API 触发限流，等待 30 秒（第 1/5 次重试）
WARNING davybase.llm 智谱 API 触发限流，等待 60 秒（第 2/5 次重试）
WARNING davybase.llm 智谱 API 触发限流，等待 120 秒（第 3/5 次重试）
WARNING davybase.llm 智谱 API 触发限流，等待 240 秒（第 4/5 次重试）
WARNING davybase.llm 智谱 API 触发限流，等待 300 秒（第 5/5 次重试）
ERROR davybase.llm 解析 digest 响应失败：智谱 API 调用失败：超过最大重试次数
```

**根本原因**:
- 智谱 GLM-5 TPM 配额约 100-200 tokens/分钟
- 每次 digest 请求约 100 tokens
- 需要 60 秒才能恢复 TPM 配额
- 默认 15s/30s 延迟远远不足

**实测数据**:
| 延迟配置 | 限流触发频率 | 处理速度 |
|---------|-------------|---------|
| 15s | 每 2-3 次触发 1 次 | 极慢 |
| 30s | 每 3-5 次触发 1 次 | 慢 |
| 60s | 极少触发 | 稳定 |

**解决方案 C+**（推荐组合）:

| 措施 | 配置修改 | 理由 |
|------|---------|------|
| 降低 Worker 批次大小 | `workers[].batch_size: 1` | 减少单次 TPM 消耗 |
| 增加 Provider 延迟 | `provider_rate_limit_delays.zhipu: 60.0` | 60 秒恢复 TPM |
| 降低 LLM 权重 | `llm.weights.zhipu: 0.05` | 仅 5% 请求分配给智谱 |
| 使用加权轮询 | `digest.provider_rotation: weighted` | 优先分配给千问/MiniMax |

**推荐配置组合**:
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
        batch_size: 1       # 降至 1
      - name: minimax
        provider: minimax
        batch_size: 2
    
    provider_rate_limit_delays:
      zhipu: 60.0           # 60 秒间隔
      qwen: 3.0
      minimax: 3.0
    
    provider_rotation: weighted

llm:
  weights:
    qwen: 0.45
    minimax: 0.5
    zhipu: 0.05             # 仅 5%
```

**效果对比** (50 条笔记):
| 配置阶段 | 智谱处理数 | 总耗时 | 限流次数 |
|---------|-----------|--------|---------|
| 初始配置 | 1/20 | 25 分钟 | 10+ 次 |
| 方案 C+ | 2-3/50 | 13.5 分钟 | 0-2 次 |

---

## 限流排查流程图

```
开始
  │
  ▼
查看日志中的限流消息
  │
  ├─ "get 笔记 API 触发限流" ──→ 调整 ingest 配置
  │                              - concurrency: 1
  │                              - rate_limit_delay: 3-5s
  │
  ├─ "LLM API 触发限流" ──→ 哪个提供商？
  │                        │
  │                        ├─ 智谱 ──→ 方案 C+
  │                        │            - batch_size: 1
  │                        │            - delay: 60s
  │                        │            - weight: 0.05
  │                        │
  │                        ├─ 千问 ──→ 调整 delay: 3s
  │                        │
  │                        └─ MiniMax ──→ 调整 delay: 3s
  │
  ▼
运行测试（limit: 10）
  │
  ▼
观察日志输出
  │
  ├─ 无限流 ──→ 配置正确，开始全量处理
  │
  └─ 仍限流 ──→ 进一步增加 delay 或降低 concurrency
```

---

## 配置调试方法

### 小规模测试

```bash
# 仅处理 10 条笔记测试配置
python main.py digest --limit 10 --apply
```

### 观察日志

```bash
# 实时查看 digest 日志
tail -f logs/digest.log

# 搜索限流消息
grep "触发限流" logs/digest.log

# 查看模型级统计
grep "模型级统计" logs/digest.log
```

### 预期输出（配置正确）

```
INFO davybase.orchestrator [Worker qwen] 启动，批次大小=2
INFO davybase.orchestrator [Worker zhipu] 启动，批次大小=1
INFO davybase.orchestrator [Worker minimax] 启动，批次大小=2
INFO davybase.orchestrator [Worker qwen] ✓ note_12345: 标题=XXX
INFO davybase.orchestrator [Worker minimax] ✓ note_12346: 标题=XXX
消化笔记：100%|██████████| 10/10 [02:15<00:00, qwen✓=4, zhipu✓=1, minimax✓=5, ✗=0]
```

### 预期输出（仍限流）

```
WARNING davybase.llm 智谱 API 触发限流，等待 30 秒
WARNING davybase.llm 智谱 API 触发限流，等待 60 秒
```

**应对**: 增加 `provider_rate_limit_delays.zhipu` 至 90s 或 120s

---

## 动态批次调整 (v4.2)

**功能**: 根据处理速度自动调整批次大小

**配置**:
```yaml
pipeline:
  digest:
    dynamic_batch:
      enabled: true             # 是否启用
      strategy: threshold       # threshold=稳健，aggressive=激进
      min_batch_size: 1
      max_batch_size: 8
      adjustment_window: 10     # 滑动窗口
      speed_threshold: 1.2      # 超过平均 20% 才增加
      rate_limit_decay: 0.5     # 限流时减半
      cooldown_seconds: 30.0    # 冷却时间
```

**工作流程**:
```
连续成功处理 → 速度超过平均 20% → 增加批次 (+1)
触发限流 → 立即减半批次 (×0.5)
冷却时间 30s → 不调整批次
```

---

## 故障排查清单

### Ingest 阶段限流

- [ ] `concurrency` 是否 > 1？ → 降至 1
- [ ] `rate_limit_delay` 是否 < 3s？ → 增至 3-5s
- [ ] `page_delay` 是否 < 5s？ → 增至 5s
- [ ] `batch_size` 是否 > 10？ → 降至 5-10

### Digest 阶段限流（通用）

- [ ] `concurrency` 是否 > 3？ → 降至 2-3
- [ ] `provider_rotation` 是否为 `single`？ → 改为 `round_robin`
- [ ] 是否只有一个 LLM？ → 添加多个 LLM

### Digest 阶段限流（智谱专项）

- [ ] `workers[].batch_size` 是否 > 1？ → 降至 1
- [ ] `provider_rate_limit_delays.zhipu` 是否 < 60s？ → 增至 60s
- [ ] `llm.weights.zhipu` 是否 > 0.1？ → 降至 0.05
- [ ] `provider_rotation` 是否为 `weighted`？ → 使用加权策略

### Compile 阶段限流

- [ ] `concurrent_batches` 是否 > 1？ → 降至 1
- [ ] `batch_size` 是否 > 5？ → 降至 3-5
- [ ] `provider_rotation` 是否为 `single`？ → 改为 `round_robin`

---

## 监控指标

### 关键日志指标

```bash
# 限流次数统计
grep -c "触发限流" logs/*.log

# 各模型成功率
grep "模型级统计" logs/digest.log -A 10
```

### 进度条指标

```
消化笔记：100%|██████████| 50/50 [05:30<00:00, qwen✓=23, zhipu✓=2, minimax✓=25, ✗=0]
```

**健康指标**:
- ✗ = 0（失败为 0）
- 各模型 ✓ 计数与权重匹配
- 总耗时 < 10 分钟（50 条）

**警告指标**:
- ✗ > 3（失败过多）
- 单一模型 ✓ 计数过高（负载不均）
- 总耗时 > 15 分钟（速度过慢）

---

## 最佳实践

### 1. 首次运行

```bash
# 小规模测试（10 条）
python main.py digest --limit 10 --apply

# 观察日志，确认无限流
tail -f logs/digest.log

# 全量运行
python main.py digest --apply
```

### 2. 日常调优

**场景 1: 频繁限流**
- 降低并发度
- 增加延迟
- 降低批次大小

**场景 2: 处理速度慢**
- 增加并发度（逐步测试）
- 使用 Worker 池模式
- 检查网络延迟

**场景 3: 单一模型失败率高**
- 降低该模型权重
- 增加该模型延迟
- 暂时禁用该模型

### 3. 配置备份

```bash
# 备份当前配置
cp config.yaml config.yaml.backup

# 修改配置前备份
cp config.yaml config.yaml.pre-rate-limit-fix

# 测试失败后恢复
cp config.yaml.backup config.yaml
```

---

## 相关文档

- [CONFIGURATION.md](CONFIGURATION.md) - 完整配置指南
- [PIPELINE_CONFIG.md](PIPELINE_CONFIG.md) - 管线配置详解
- [WORKER_POOL_IMPLEMENTATION.md](WORKER_POOL_IMPLEMENTATION.md) - Worker 池模式实施文档
