# 基于时间戳的增量同步机制

**版本**: v5.1  
**创建日期**: 2026-04-17  
**状态**: 生产中

---

## 概述

Davybase v5.1 引入了基于时间戳的增量同步机制，用于高效地从 get 笔记 API 获取新增笔记。

### 核心原理

```
┌─────────────────────────────────────────────────────────────────────────┐
│  增量同步流程                                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  第 1 次运行（全量同步）：                                                │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  1. 获取所有笔记                                            │       │
│  │  2. 抽取所有未处理的笔记                                    │       │
│  │  3. 记录完成时间戳：2026-04-17T08:00:00 ← 基准线            │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                          │                                              │
│                          ▼                                              │
│  第 2 次运行（增量同步）：                                                │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  1. 读取基准线：2026-04-17T08:00:00                         │       │
│  │  2. 获取所有笔记                                            │       │
│  │  3. 过滤：仅处理 created_at > 2026-04-17T08:00:00 的笔记   │       │
│  │  4. 更新基准线：2026-04-17T09:00:00 ← 新基准线              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                          │                                              │
│                          ▼                                              │
│  第 3 次运行（增量同步）：                                                │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  1. 读取基准线：2026-04-17T09:00:00                         │       │
│  │  2. 获取所有笔记                                            │       │
│  │  3. 过滤：仅处理 created_at > 2026-04-17T09:00:00 的笔记   │       │
│  │  4. 更新基准线：2026-04-17T10:00:00 ← 新基准线              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 使用方式

### 方式 1: 使用 `ingest` 命令

```bash
# 第 1 步：首次全量同步（建立基准线）
python main.py ingest

# 第 2 步：每日增量同步（仅抽取新笔记）
python main.py ingest --incremental
```

### 方式 2: 使用 `pipeline` 命令

```bash
# 第 1 步：首次全量管道（建立基准线）
python main.py pipeline --full

# 第 2 步：每日增量管道（仅抽取新笔记）
python main.py pipeline --incremental
```

### 方式 3: 使用 AI Native Skills

```bash
# 第 1 步：首次全量同步
/getnote-organizer

# 第 2 步：每日增量同步
# 在 Claude 中说："执行增量同步，只获取上次同步后的新笔记"
```

---

## 技术实现

### 数据库表结构

增量同步基准线存储在 `sync_state.db` 的 `incremental_sync_state` 表中：

```sql
CREATE TABLE IF NOT EXISTS incremental_sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行表
    last_sync_at DATETIME,                   -- 上次同步时间戳
    last_sync_type TEXT,                     -- 同步类型：'full' 或 'incremental'
    notes_extracted INTEGER,                 -- 本次抽取的笔记数量
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 时间戳比较逻辑

笔记的 `created_at` 字段格式：`2026-04-15 13:03:47`

基准线时间戳格式：`2026-04-17T08:00:00`

比较逻辑：
```python
# 笔记创建时间 > 基准线时间 = 新笔记
note_dt > last_sync_dt → 抽取
```

### 代码示例

```python
from src.orchestrator import IngestOrchestrator
from src.config import Config

config = Config()
state_dir = Path(config.vault_path) / ".davybase" / "progress"
orchestrator = IngestOrchestrator(state_dir, config)

# 全量同步
result = await orchestrator.run(incremental=False)

# 增量同步（自动读取上次同步时间戳）
result = await orchestrator.run(incremental=True)
```

---

## 状态查询

### 查看当前基准线

```bash
python -c "
from src.sync_state import SyncState
sync_state = SyncState('/Users/qiming/ObsidianWiki/.davybase/sync_state.db')
print('上次同步时间:', sync_state.get_last_sync_timestamp())
print('同步类型:', sync_state.get_last_sync_type())
"
```

### 查看同步日志

```bash
# 查看最近一次增量同步日志
tail -f logs/ingest.log | grep "增量同步"

# 查看基准线更新记录
grep "已更新增量同步基准线" logs/*.log
```

---

## 常见问题

### Q: 第一次运行时没有基准线怎么办？

**A**: 第一次运行时，`--incremental` 参数会检测到没有基准线，自动降级为全量同步，并在完成后建立基准线。

### Q: 如何重置基准线，重新全量同步？

**A**: 删除基准线记录：
```bash
python -c "
from src.sync_state import SyncState
sync_state = SyncState('/Users/qiming/ObsidianWiki/.davybase/sync_state.db')
sync_state.clear_sync_timestamp()
print('基准线已清除，下次运行将执行全量同步')
"
```

### Q: 增量同步和全量同步有什么区别？

| 特性 | 全量同步 | 增量同步 |
|------|---------|---------|
| 基准线 | 不需要 | 必须 |
| 处理笔记 | 所有未处理的笔记 | 基准线之后的新笔记 |
| 速度 | 较慢 | 快 |
| 适用场景 | 首次使用/重建知识库 | 日常同步 |

### Q: 如果 get 笔记 API 返回的笔记没有时间戳怎么办？

**A**: 没有时间戳的笔记会被跳过，不会被抽取。这是为了防止重复处理。

### Q: 基准线存储在哪个文件？

**A**: `/Users/qiming/ObsidianWiki/.davybase/sync_state.db` 的 `incremental_sync_state` 表中。

---

## 最佳实践

### 1. 首次使用

```bash
# 先执行全量同步建立基准线
python main.py pipeline --full

# 验证基准线已建立
python main.py status
```

### 2. 每日自动同步

```bash
# crontab 配置（每天早上 6 点自动执行）
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py pipeline --incremental >> logs/incremental.log 2>&1
```

### 3. 监控同步状态

```bash
# 查看最近一次增量同步结果
tail -20 logs/incremental.log

# 查看基准线时间
python -c "
from src.sync_state import SyncState
s = SyncState('/Users/qiming/ObsidianWiki/.davybase/sync_state.db')
print('基准线:', s.get_last_sync_timestamp())
"
```

---

## 相关文档

- [INITIALIZATION.md](INITIALIZATION.md) - 新手指引
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - Skills 使用指南
- [CONCURRENT_PIPELINE.md](CONCURRENT_PIPELINE.md) - 并发管线设计文档
