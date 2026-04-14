# Davybase Worker 池模式实施文档

**版本**: v4.2  
**创建日期**: 2026-04-14  
**状态**: 实施中

---

## 一、需求背景

### 用户需求

1. **流水线能力** - 处理完立刻领取新笔记，非批次等待模式
2. **直接运行 digest** - 50 条笔记已在 `raw/notes/_inbox/`
3. **实时进度追踪** - 每个模型独立进度显示
4. **3 模型并行** - 千问、智谱、MiniMax 各一个 Worker
5. **批次大小** - 每个 Worker 每次处理 2 条笔记

### 当前架构问题

当前 `DigestOrchestrator.run()` 采用批次模式：

```
批次 0 (笔记 1-2) → 千问 ──┐
批次 1 (笔记 3-4) → 智谱 ──┼── 并发执行，批次间等待
批次 2 (笔记 5-6) → MiniMax ─┘
批次 3 (笔记 7-8) → 千问 ──┐
...
```

**问题**：批次 0 处理慢时，批次 1、2 必须等待，无法实现"处理完立刻领取"。

### 目标架构

```
┌─────────────────────────────────────────────┐
│         任务队列 (asyncio.Queue)            │
│  [笔记 1] [笔记 2] ... [笔记 50]             │
└─────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Worker 1   │ │  Worker 2   │ │  Worker 3   │
│  千问       │ │  智谱       │ │  MiniMax    │
│  批次=2     │ │  批次=2     │ │  批次=2     │
└─────────────┘ └─────────────┘ └─────────────┘
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
              处理完立即领取下一批
```

---

## 二、讨论过程

### 配置方案讨论

**初始需求**：
- 50 条笔记测试
- 3 个模型并行
- 每批次 2 条
- 处理完立刻领取

**配置参数映射**：
| 需求 | 配置参数 |
|------|---------|
| 50 条笔记测试 | `limit: 50` |
| 3 个模型并行 | `workers: [qwen, zhipu, minimax]` |
| 每批次 2 条 | `batch_size: 2` (per worker) |
| 处理完立刻领取 | `worker_mode: pool` |

### 架构决策

**方案 A: Worker 池模式（已选）**
- 每个模型独立 Worker
- 动态队列领取任务
- 真正的流水线作业

**方案 B: 批次并发（放弃）**
- 预先分批次
- 批次间等待
- 非真正流水线

### 进度追踪设计

**需求**：实时看到每个模型的处理进度

**实现**：
```python
progress = {
    "qwen": {"processed": 0, "success": 0, "failed": 0},
    "zhipu": {"processed": 0, "success": 0, "failed": 0},
    "minimax": {"processed": 0, "success": 0, "failed": 0},
}
postfix = {"qwen✓": 8, "zhipu✓": 7, "minimax✓": 8, "✗": 0}
pbar.set_postfix(postfix)
```

---

## 三、配置方案

### config.yaml

```yaml
pipeline:
  # 阶段 2: 消化 - Worker 池模式
  digest:
    worker_mode: pool           # pool=Worker 池模式，batch=批次模式
    workers:                    # 每个 Worker 独立配置
      - name: qwen
        provider: qwen
        batch_size: 2           # 每次处理 2 条
      - name: zhipu
        provider: zhipu
        batch_size: 2
      - name: minimax
        provider: minimax
        batch_size: 2
    limit: 50                   # 限制 50 条
    apply: true                 # 直接移动

  # 阶段 1: 摄取
  ingest:
    batch_size: 10
    concurrency: 2
    rate_limit_delay: 2.0
    page_delay: 3.0

  # 阶段 3: 编译
  compile:
    batch_size: 5
    concurrent_batches: 1
    provider_rotation: round_robin
    threshold: 3
```

### CLI 命令覆盖

```bash
# 使用配置文件默认值
python main.py digest --apply

# CLI 覆盖配置
python main.py digest \
  --worker-mode pool \
  --limit 50 \
  --apply

# 覆盖 Worker 配置
python main.py digest \
  --workers '[{"name":"qwen","provider":"qwen","batch_size":2}]' \
  --apply
```

---

## 四、实施计划

### Phase 1: 修改配置加载

**目标**：`DigestOrchestrator` 读取 Worker 配置

**文件**：
- `src/orchestrator.py` - `DigestOrchestrator.__init__`
- `config.yaml` - 新增 `digest.workers`

**验收标准**：
- [ ] 配置可正确加载
- [ ] `self.worker_configs` 包含 3 个 Worker 配置

---

### Phase 2: 实现 Worker 协程

**目标**：`_worker` 方法实现单 Worker 逻辑

**文件**：
- `src/orchestrator.py` - 新增 `_worker` 方法

**验收标准**：
- [ ] Worker 可从队列领取任务
- [ ] 每次处理 `batch_size` 条笔记
- [ ] 处理完立即领取下一批
- [ ] 更新进度追踪

---

### Phase 3: 实现 Worker 池运行方法

**目标**：`_run_worker_pool` 方法调度多 Worker

**文件**：
- `src/orchestrator.py` - 新增 `_run_worker_pool` 方法

**验收标准**：
- [ ] 创建任务队列
- [ ] 启动 3 个 Worker
- [ ] 等待所有 Worker 完成
- [ ] 聚合结果并返回

---

### Phase 4: 集成到 run() 方法

**目标**：`run()` 方法支持 Worker 池模式

**文件**：
- `src/orchestrator.py` - 修改 `run()` 方法

**验收标准**：
- [ ] `worker_mode == "pool"` 时调用 `_run_worker_pool`
- [ ] `worker_mode == "batch"` 时调用原有批次逻辑
- [ ] 向后兼容

---

### Phase 5: 更新 CLI 命令

**目标**：CLI 支持 Worker 模式参数

**文件**：
- `main.py` - `digest` 命令新增参数

**验收标准**：
- [ ] `--worker-mode` 参数
- [ ] `--workers` 参数（JSON 字符串）
- [ ] 帮助文档更新

---

### Phase 6: 配置和文档更新

**目标**：完整配置和文档

**文件**：
- `config.yaml` - 完整配置
- `docs/PIPELINE_CONFIG.md` - Worker 池模式说明
- `docs/WORKER_POOL_IMPLEMENTATION.md` - 本文档

**验收标准**：
- [ ] 配置示例完整
- [ ] 文档包含使用示例
- [ ] 预期输出示例

---

### Phase 7: 测试验证

**目标**：端到端验证 50 条笔记

**命令**：
```bash
python main.py digest --apply --limit 50
```

**验收标准**：
- [ ] 3 个 Worker 同时启动
- [ ] 进度条显示每模型处理数量
- [ ] 处理完 50 条笔记
- [ ] 失败率 < 5%
- [ ] 总耗时 < 10 分钟

---

## 五、代码实现细节

### Phase 1: 配置加载

```python
class DigestOrchestrator:
    def __init__(self, state_dir: Path, config: Config):
        # ... 现有代码 ...
        
        # 从配置文件读取 Worker 配置
        pipeline_config = getattr(config, 'raw_config', {}).get('pipeline', {}).get('digest', {})
        self.worker_mode = pipeline_config.get('worker_mode', 'batch')
        self.worker_configs = pipeline_config.get('workers', [
            {"name": "qwen", "provider": "qwen", "batch_size": 2},
            {"name": "zhipu", "provider": "zhipu", "batch_size": 2},
            {"name": "minimax", "provider": "minimax", "batch_size": 2},
        ])
```

---

### Phase 2-3: Worker 协程和池运行

```python
async def _run_worker_pool(
    self,
    pending_files: List[Path],
    apply: bool,
    limit: Optional[int]
) -> Dict[str, Any]:
    """Worker 池模式：每个模型独立领取任务"""
    import asyncio
    
    # 创建任务队列
    task_queue = asyncio.Queue()
    files_to_process = pending_files[:limit] if limit else pending_files
    for f in files_to_process:
        await task_queue.put(f)
    
    # 进度追踪（按模型分离）
    progress = {
        "qwen": {"processed": 0, "success": 0, "failed": 0},
        "zhipu": {"processed": 0, "success": 0, "failed": 0},
        "minimax": {"processed": 0, "success": 0, "failed": 0},
    }
    progress_lock = asyncio.Lock()
    
    # 进度条初始化
    pbar = None
    if HAS_TQDM:
        pbar = tqdm(total=len(files_to_process), desc="消化笔记", unit="条")
    
    # 创建 Workers
    workers = []
    for worker_config in self.worker_configs:
        name = worker_config["name"]
        provider_name = worker_config["provider"]
        provider = self.providers[provider_name]
        batch_size = worker_config.get("batch_size", 2)
        
        task = asyncio.create_task(
            self._worker(
                name=name,
                provider=provider,
                task_queue=task_queue,
                batch_size=batch_size,
                apply=apply,
                progress=progress,
                progress_lock=progress_lock,
                pbar=pbar
            )
        )
        workers.append(task)
    
    # 等待所有 Workers 完成
    await asyncio.gather(*workers, return_exceptions=True)
    
    # 关闭进度条
    if pbar:
        pbar.close()
    
    # 聚合结果
    total_processed = sum(p["processed"] for p in progress.values())
    total_success = sum(p["success"] for p in progress.values())
    total_failed = sum(p["failed"] for p in progress.values())
    
    logger.info(f"消化完成：处理 {total_processed} 条，成功 {total_success} 条，失败 {total_failed} 条")
    
    return {
        "total_processed": total_processed,
        "total_classified": total_success,
        "total_moved": total_success if apply else 0,
        "failed": total_failed,
        "by_provider": progress
    }

async def _worker(
    self,
    name: str,
    provider: LLMProvider,
    task_queue: asyncio.Queue,
    batch_size: int,
    apply: bool,
    progress: Dict,
    progress_lock: asyncio.Lock,
    pbar
) -> None:
    """Worker 协程：从队列领取任务，处理完立即领取下一批"""
    logger.info(f"[Worker {name}] 启动，批次大小={batch_size}")
    
    while True:
        # 领取一批笔记（batch_size 条）
        batch = []
        for _ in range(batch_size):
            try:
                file = task_queue.get_nowait()
                batch.append(file)
                task_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        if not batch:
            logger.info(f"[Worker {name}] 队列为空，退出")
            return
        
        # 处理本批次
        for file in batch:
            result = await self._digest_single_file(file, provider, apply)
            
            # 更新进度
            async with progress_lock:
                progress[name]["processed"] += 1
                if result["success"]:
                    progress[name]["success"] += 1
                else:
                    progress[name]["failed"] += 1
                
                # 更新进度条
                if pbar:
                    pbar.update(1)
            
            # 日志输出
            note_id = self._extract_note_id(file)
            if result["success"]:
                logger.info(
                    f"[Worker {name}] ✓ {note_id}: "
                    f"标题={result.get('title', 'N/A')}, "
                    f"分类={result.get('kb', 'N/A')}"
                )
            else:
                logger.error(f"[Worker {name}] ✗ {note_id}: {result.get('error', '未知错误')}")
```

---

### Phase 4: 集成到 run()

```python
async def run(
    self,
    inbox_dir: str = None,
    apply: bool = None,
    limit: Optional[int] = None,
    provider_rotation: str = None,
    concurrency: int = None
) -> Dict[str, Any]:
    # ... 现有准备逻辑 ...
    
    # 根据模式选择执行方式
    if self.worker_mode == "pool":
        return await self._run_worker_pool(
            pending_files=pending_files,
            apply=apply,
            limit=limit
        )
    else:
        # 原有批次模式
        return await self._run_batch_mode(
            pending_files=pending_files,
            apply=apply,
            concurrency=concurrency,
            pbar=pbar
        )
```

---

### Phase 5: CLI 更新

```python
@cli.command()
@click.option("--inbox-dir", default=None, help="待处理笔记目录")
@click.option("--worker-mode", default=None, help="Worker 模式：pool|batch")
@click.option("--workers", default=None, help="Worker 配置 JSON 字符串")
@click.option("--concurrency", default=None, type=int, help="并发任务数")
@click.option("--apply", is_flag=True, default=None, help="直接执行移动")
@click.option("--limit", type=int, default=None, help="限制处理数量")
def digest(inbox_dir: str, worker_mode: str, workers: str, concurrency: int, apply: bool, limit: int):
    """并发消化笔记（v4.0）"""
    config = Config()
    state_dir = Path(config.vault_path) / ".davybase" / "progress"
    orchestrator = DigestOrchestrator(state_dir, config)
    
    # CLI 覆盖配置
    if worker_mode:
        orchestrator.worker_mode = worker_mode
    if workers:
        orchestrator.worker_configs = json.loads(workers)
    
    result = asyncio.run(orchestrator.run(
        inbox_dir=inbox_dir,
        apply=apply,
        limit=limit,
        concurrency=concurrency
    ))
    
    # 显示详细结果
    click.echo(f"消化完成：处理 {result['total_processed']} 条，移动 {result['total_moved']} 条，失败 {result['failed']} 条")
    if 'by_provider' in result:
        for provider, stats in result['by_provider'].items():
            click.echo(f"  {provider}: ✓{stats['success']} ✗{stats['failed']}")
```

---

## 六、预期输出

### 启动日志

```
INFO davybase.orchestrator 开始并发消化 (concurrency=3, provider_rotation=round_robin)
INFO davybase.orchestrator 扫描到 9349 条笔记
INFO davybase.orchestrator 待处理：9349 条
INFO davybase.orchestrator [Worker qwen] 启动，批次大小=2
INFO davybase.orchestrator [Worker zhipu] 启动，批次大小=2
INFO davybase.orchestrator [Worker minimax] 启动，批次大小=2
```

### 运行时日志

```
INFO davybase.orchestrator [Worker qwen] ✓ note_12345: 标题=反向传播算法，分类=AI+ 机器学习
INFO davybase.orchestrator [Worker zhipu] ✓ note_12346: 标题=梯度下降优化，分类=AI+ 机器学习
INFO davybase.orchestrator [Worker minimax] ✓ note_12347: 标题=Transformer 架构，分类=编程+AI
```

### 进度条

```
消化笔记：45%|████▌     | 23/50 [02:15<01:30, qwen✓=8, zhipu✓=7, minimax✓=8, ✗=0]
```

### 完成输出

```
消化完成：处理 50 条，成功 48 条，失败 2 条
  qwen: ✓16 ✗1
  zhipu: ✓15 ✗1
  minimax: ✓17 ✗0
```

---

## 七、Git 提交策略

每个 Phase 完成后独立提交：

```bash
# Phase 1 完成
git add config.yaml src/orchestrator.py
git commit -m "feat(v4.2): Phase 1 - 配置加载支持 Worker 模式"
git push

# Phase 2 完成
git add src/orchestrator.py
git commit -m "feat(v4.2): Phase 2 - 实现 Worker 协程"
git push

# ... 以此类推
```

---

## 八、回滚方案

如果 Worker 池模式失败，回退到批次模式：

```yaml
# config.yaml
pipeline:
  digest:
    worker_mode: batch  # 回退到批次模式
```

或使用 CLI：
```bash
python main.py digest --worker-mode batch
```

---

## 九、后续优化

1. **动态批次** - 根据处理速度自动调整 `batch_size`
2. **失败重试** - Worker 内失败任务重新入队
3. **优先级队列** - 重要笔记优先处理
4. **多进程** - 突破 GIL 限制

---

**文档状态**: 已完成  
**下一步**: 开始实施 Phase 1
