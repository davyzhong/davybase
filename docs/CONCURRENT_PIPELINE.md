# Davybase 并发管线设计文档

**版本**: v4.0  
**创建日期**: 2026-04-13  
**状态**: 设计中

---

## 执行摘要

本文档描述 Davybase v4.0 的并发管线设计，支持：
1. **分批次执行** - 大任务拆分为小批次，便于中断恢复和进度追踪
2. **并发任务模式** - 同一批次内多条笔记并发处理
3. **多 LLM 负载均衡** - 并发任务分配不同 LLM，减少单点限流影响
4. **幂等性** - 每个任务执行前检查状态，避免重复处理
5. **独立可执行** - 每个阶段可独立运行，支持断点续传

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Pipeline Orchestrator (调度中枢)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  - 读取待处理队列（基于 processing_status.is_processed()）              │
│  - 按批次拆分（batch_size 可配置）                                      │
│  - 分配 LLM 提供商（轮询/加权）                                          │
│  - 启动并发任务（asyncio.Semaphore 控制并发度）                         │
│  - 聚合结果并更新状态                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Batch 1     │     │   Batch 2     │     │   Batch 3     │
│   (LLM: 智谱)  │     │  (LLM: MiniMax)│    │   (LLM: 智谱)  │
│   并发度：5    │     │   并发度：5    │     │   并发度：5    │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ProcessingStatus 状态更新                           │
│  - ingest.json  /  digest.json  /  compile.json  /  publish.json        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 配置说明

### config.yaml 配置

```yaml
# 并发管线配置
pipeline:
  ingest:
    batch_size: 20
    concurrency: 3          # 并发请求数
    rate_limit_delay: 1.0   # API 请求间隔（秒）

  digest:
    batch_size: 10
    concurrency: 5          # 并发任务数
    provider_rotation: round_robin  # 多 LLM 分配策略

  compile:
    batch_size: 15
    concurrent_batches: 2   # 同时编译的批次数量
    provider_rotation: round_robin
```

### LLM 分配策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `single` | 始终使用指定的单一 LLM | 调试、测试单一 LLM 效果 |
| `round_robin` | 智谱和 MiniMax 轮询分配 | **默认推荐**，分散限流风险 |
| `weighted` | 加权分配（智谱 70%, MiniMax 30%） | 一个 LLM 配额更充足时 |

---

## Phase 分解

### Phase 1: 并发抽取器 (`src/orchestrator.py::IngestOrchestrator`)

**目标**: 支持并发抽取笔记，减少 API 调用时间

**核心逻辑**:
```python
class IngestOrchestrator:
    def __init__(self, state_dir: Path, config: Config):
        self.state = IngestStatus(state_dir)
        self.config = config
        self.semaphore = asyncio.Semaphore(3)  # 并发度=3

    async def run(self, batch_size: int = 20, concurrency: int = 3, 
                  resume: bool = True, source: str = "getnote") -> Dict:
        # 1. 获取已抽取 ID 列表（幂等性检查）
        extracted_ids = self.state.get_extracted_ids()
        
        # 2. 获取待抽取笔记
        notes_to_extract = [n for n in all_notes if n["note_id"] not in extracted_ids]
        
        # 3. 分批次
        batches = self._chunk(notes_to_extract, batch_size)
        
        # 4. 并发抽取
        tasks = [self._extract_batch(batch, semaphore) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 5. 更新状态
        return self._aggregate_results(results)
```

**状态检查**:
- 抽取前检查 `IngestStatus.is_extracted(note_id)`
- 抽取后调用 `IngestStatus.mark_processed()`

---

### Phase 2: 并发消化器 (`src/orchestrator.py::DigestOrchestrator`)

**目标**: 并发生成标题、分类、原子化拆解

**核心逻辑**:
```python
class DigestOrchestrator:
    def __init__(self, state_dir: Path, config: Config):
        self.state = DigestStatus(state_dir)
        self.providers = {
            "zhipu": ZhipuProvider(config.get_llm_api_key("zhipu")),
            "minimax": MiniMaxProvider(config.get_llm_api_key("minimax"))
        }
        self.semaphore = asyncio.Semaphore(5)  # 并发度=5

    def _select_provider(self, index: int, strategy: str) -> LLMProvider:
        """根据策略选择 LLM 提供商"""
        if strategy == "round_robin":
            keys = list(self.providers.keys())
            return self.providers[keys[index % len(keys)]]
        elif strategy == "single":
            return self.providers["zhipu"]
        # weighted 策略实现...
```

**多 LLM 提示词分工**:
- **生成标题** → 轮询分配
- **分类推荐** → 轮询分配
- **原子化拆解** → 轮询分配

---

### Phase 3: 并发编译器 (`src/orchestrator.py::CompileOrchestrator`)

**目标**: 多批次并发编译，不同批次使用不同 LLM

**核心逻辑**:
```python
class CompileOrchestrator:
    def __init__(self, state_dir: Path, config: Config):
        self.state = CompileStatus(state_dir)
        self.providers = {...}
        self.batch_semaphore = asyncio.Semaphore(2)  # 最多 2 个批次并发

    async def run(self, kb_dir: str, threshold: int = 3, 
                  provider_rotation: str = "round_robin",
                  concurrent_batches: int = 2) -> Dict:
        # 1. 读取笔记
        notes = self._load_notes(kb_dir)
        
        # 2. 分批次
        batches = self._chunk(notes, batch_size=15)
        
        # 3. 并发编译批次（不同批次使用不同 LLM）
        tasks = [
            self._compile_batch(batch, self._select_provider(i, provider_rotation))
            for i, batch in enumerate(batches)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. 合并结果
        merged = await self._merge_batches(results)
        
        # 5. 保存 Wiki 条目
        self._save_wiki_entries(merged)
```

**LLM 分配示例**:
| 批次 | LLM | 理由 |
|------|-----|------|
| Batch 1 | 智谱 GLM5 | 第一个批次 |
| Batch 2 | MiniMax M2.7 | 避免单点限流 |
| Batch 3 | 智谱 GLM5 | 轮询 |

---

### Phase 4: CLI 编排器 (`src/orchestrator.py`)

**目标**: 统一的 CLI 入口，支持分阶段独立执行

**命令设计**:
```bash
# 阶段 1: 并发抽取
python main.py ingest --batch-size 20 --concurrency 3 --resume

# 阶段 2: 并发消化
python main.py digest --batch-size 10 --concurrency 5 \
    --provider-rotation round_robin --resume

# 阶段 3: 并发编译
python main.py compile --batch-size 15 --concurrent-batches 2 \
    --provider-rotation round_robin --resume

# 全量管道（一键执行所有阶段）
python main.py pipeline --full --resume
```

**`--resume` 逻辑**:
- 读取 `processing_status.json` 或 `*.json` 状态文件
- 跳过所有 `is_processed() == true` 的项目
- 仅处理待处理队列

---

## 幂等性检查清单

每个阶段执行前检查：

### Ingest 阶段
- [ ] 检查 `IngestStatus.is_extracted(note_id)`
- [ ] 已抽取的笔记跳过

### Digest 阶段
- [ ] 检查 `DigestStatus.is_summarized(note_id)` - 已生成标题的跳过
- [ ] 检查 `DigestStatus.is_classified(note_id)` - 已分类的跳过
- [ ] 检查 `DigestStatus.is_moved(note_id)` - 已移动的跳过

### Compile 阶段
- [ ] 检查 `CompileStatus.is_processed(wiki_title)` - 已编译的跳过

---

## 错误处理与降级

```python
# 并发任务错误隔离
results = await asyncio.gather(*tasks, return_exceptions=True)

for note, result in zip(notes, results):
    if isinstance(result, Exception):
        logger.error(f"处理 {note['note_id']} 失败：{result}")
        # 记录错误，不影响其他任务
        self.state.mark_error(note['note_id'], str(result))
    else:
        self.state.mark_processed(note['note_id'], result)

# LLM 降级
async def _compile_with_fallback(self, notes: list, initial_provider: str):
    providers = ["zhipu", "minimax"] if initial_provider == "zhipu" else ["minimax", "zhipu"]
    
    for provider_name in providers:
        try:
            return await self.providers[provider_name].compile_notes(notes)
        except Exception as e:
            logger.warning(f"{provider_name} 失败：{e}")
            continue
    
    raise RuntimeError("所有 LLM 提供商均失败")
```

---

## 预期效果

**假设场景**：100 条待处理笔记

| 指标 | 当前（串行） | 改造后（并发） | 节省 |
|------|-------------|---------------|------|
| **抽取时间** | ~200 秒（2 秒/条） | ~40 秒（并发度 5） | 80% |
| **消化时间** | ~300 秒（3 秒/条，单 LLM） | ~60 秒（并发度 5，双 LLM） | 80% |
| **编译时间** | ~180 秒（15 条/批，单 LLM） | ~60 秒（2 批次并发，双 LLM） | 67% |
| **总时间** | ~680 秒 | ~160 秒 | **~76%** |

---

## MCP Tools 集成

### ingest_notes

```python
@mcp.tool()
async def ingest_notes(
    batch_size: int = 20,
    resume: bool = True,
    source: str = "getnote",
    concurrency: int = 3
) -> str:
    """从指定源抽取笔记到 raw/notes/_inbox/"""
    orchestrator = IngestOrchestrator(state_dir, config)
    result = await orchestrator.run(
        batch_size=batch_size,
        concurrency=concurrency,
        resume=resume,
        source=source
    )
    return json.dumps({
        "status": "completed",
        "total_extracted": result.get("total", 0),
        "failed": result.get("failed", 0),
        "duration_seconds": result.get("duration", 0)
    }, ensure_ascii=False, indent=2)
```

### digest_notes

```python
@mcp.tool()
async def digest_notes(
    inbox_dir: str = "raw/notes/_inbox/",
    apply: bool = False,
    limit: Optional[int] = None,
    provider: str = "minimax",
    provider_rotation: str = "round_robin",
    concurrency: int = 5
) -> str:
    """为散落笔记生成标题、分类、原子化拆解"""
    orchestrator = DigestOrchestrator(state_dir, config)
    result = await orchestrator.run(
        inbox_dir=inbox_dir,
        apply=apply,
        limit=limit,
        provider=provider,
        provider_rotation=provider_rotation,
        concurrency=concurrency
    )
    return json.dumps({
        "status": "completed",
        "total_processed": result.get("total_processed", 0),
        "total_classified": result.get("total_classified", 0),
        "total_moved": result.get("total_moved", 0),
        "failed": result.get("failed", 0),
        "duration_seconds": result.get("duration", 0)
    }, ensure_ascii=False, indent=2)
```

### compile_notes

```python
@mcp.tool()
async def compile_notes(
    kb_dir: str,
    threshold: int = 3,
    provider: str = "zhipu",
    provider_rotation: str = "round_robin",
    concurrent_batches: int = 2
) -> str:
    """将知识库中的笔记聚合为结构化 Wiki 条目"""
    orchestrator = CompileOrchestrator(state_dir, config)
    result = await orchestrator.run(
        kb_dir=kb_dir,
        threshold=threshold,
        provider=provider,
        provider_rotation=provider_rotation,
        concurrent_batches=concurrent_batches
    )
    return json.dumps({
        "status": "completed",
        "total_wiki_entries": result.get("total_wiki_entries", 0),
        "failed": result.get("failed", 0),
        "duration_seconds": result.get("duration", 0)
    }, ensure_ascii=False, indent=2)
```

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 并发过高触发 API 限流 | Semaphore 控制并发度，指数退避重试 |
| 单一 LLM 配额耗尽 | 多 LLM 轮询，自动降级 |
| 中断后状态不一致 | 每处理一条立即更新状态文件 |
| 批次合并失败 | 保留中间结果，支持重新合并 |

---

## 文件变更清单

| 文件 | 变更类型 | 描述 |
|------|---------|------|
| `src/orchestrator.py` | 新增 | CLI 编排器，统一调度 |
| `src/extractor.py` | 修改 | 添加并发抽取逻辑 |
| `src/compiler.py` | 修改 | 添加并发编译逻辑 |
| `src/mcp_server.py` | 修改 | Tools 填充实际执行逻辑 |
| `config.yaml` | 修改 | 添加 `pipeline` 并发配置 |
| `skills/obsidianSkills/` | 新增 | Skills 定义（ingest/digest/compile） |
| `docs/CONCURRENT_PIPELINE.md` | 新增 | 并发管线设计文档 |

---

## 后续开发计划

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 更新 MCP/Skills 配置 | ✅ 完成 |
| Phase 1 | 实现并发抽取器 | 待开发 |
| Phase 2 | 实现并发消化器 | 待开发 |
| Phase 3 | 实现并发编译器 | 待开发 |
| Phase 4 | 实现 CLI 编排器 | 待开发 |
| Phase 5 | 更新配置和文档 | 进行中 |

---

## 参考文档

- [MCP Server Guide](MCP_SERVER_GUIDE.md)
- [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)
- [processing_status.py](../src/processing_status.py) - 状态追踪系统
