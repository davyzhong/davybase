# Davybase v5.0 工作流 redesign 说明

**日期**: 2026-04-17  
**变更类型**: 用户体验优化  
**影响范围**: 文档、CLI 交互

---

## 背景

在用户完成首次全量同步（6045 条笔记）后，未来所有运行都只是增量采集。然而，原有文档和代码没有清晰区分"首次全量"和"每日增量"的使用场景，可能导致新用户困惑。

## 设计目标

让拿到项目去初始化的人，能够清楚地知道：
1. **第 1 步**: 执行一次彻底的全量同步（建立基线）
2. **第 2 步**: 设置每日自动增量同步（持续更新）

---

## 变更内容

### 1. 新增文档

#### `docs/INITIALIZATION.md` - 新手指引文档

**目标读者**: 首次使用 Davybase 的新用户

**核心内容**:
- "一次性全量 + 每日增量"工作流说明
- 第 1 步：全量同步（仅执行一次）详细说明
- 第 2 步：增量同步（每日自动）配置方法
- crontab/launchd/Windows 任务计划程序配置示例
- 常见问题解答

**关键设计**:
```
┌─────────────────────────────────────────────────────────────┐
│  第 1 步：全量同步（一次性）                                  │
│  - 首次使用时执行                                            │
│  - 处理所有历史笔记                                          │
│  - 建立基线状态                                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  第 2 步：增量同步（每日自动）                                │
│  - 每日执行一次                                              │
│  - 仅处理新增/修改的笔记                                     │
│  - 保持知识库持续更新                                        │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. 更新的文档

#### `README.md` - 项目首页

**变更**:
- 在"快速开始"部分新增"📌 重要：首次使用必读"表格
- 明确标注"第 1 步：全量同步（仅一次）"和"第 2 步：增量同步（每日自动）"
- 三种使用方式（AI Native Skills、CLI、传统 CLI）都按此模式重写
- 文档索引新增 `docs/INITIALIZATION.md`

**示例**:
```markdown
### 📌 重要：首次使用必读

| 步骤 | 操作 | 频率 | 说明 |
|------|------|------|------|
| **第 1 步** | 全量同步 | **仅一次** | 首次使用时处理所有历史笔记 |
| **第 2 步** | 增量同步 | **每日自动** | 仅处理新增/修改的笔记 |
```

---

#### `docs/SKILLS_GUIDE.md` - Skills 使用指南

**变更**:
- "最佳实践"部分新增定时任务配置说明
- 明确"首次使用时，先手动执行一次全量同步"
- 提供 crontab 配置示例
- 链接到 `INITIALIZATION.md` 获取详细说明

**示例**:
```bash
# 第 1 步：首次全量同步（仅执行一次）
python main.py pipeline --full --resume

# 第 2 步：设置每日自动增量同步（crontab）
crontab -e
# 添加：0 6 * * * cd /path/to/davybase && python main.py incremental
```

---

#### `docs/USAGE.md` - 使用指南

**变更**:
- 顶部新增"📌 重要：首次使用必读"提示框
- "常见工作流"新增 v5.0 Skills 工作流说明
- "最佳实践"重构为：
  - 1. 首次同步（仅执行一次）
  - 2. 日常同步（每日自动）
- FAQ 更新：
  - 明确区分全量/增量的使用场景
  - 新增"如何知道是增量同步还是全量同步"问题

---

### 3. 代码变更

#### `main.py` - CLI 入口

**变更 1**: `incremental` 命令新增全量同步检查

```python
@click.option("--force", is_flag=True, help="跳过全量同步检查，强制执行增量")
def incremental(..., force: bool):
    # 检查是否已完成首次全量同步
    if not force:
        sync_db = Path(config.data_path) / "sync.db"
        if not sync_db.exists():
            click.echo("❌ 错误：未检测到同步状态数据库（sync.db）")
            click.echo("")
            click.echo("📌 首次使用必读：")
            click.echo("增量同步仅适用于已完成首次全量同步的场景。")
            click.echo("")
            click.echo("请先执行全量同步：")
            click.echo("  python main.py pipeline --full --resume")
            return
```

**效果**:
- 新用户直接运行 `incremental` 时会被友好提示先执行全量同步
- 高级用户可使用 `--force` 跳过检查（不推荐）

---

**变更 2**: `status` 命令新增首次使用提示

```python
def status():
    # ...
    # 首次使用提示
    if not s['last_run']:
        click.echo("")
        click.echo("=" * 60)
        click.echo("📌 首次使用提示：")
        click.echo("=" * 60)
        click.echo("你还没有执行过同步。请按以下步骤操作：")
        click.echo("")
        click.echo("  1. 首次全量同步（仅执行一次）：")
        click.echo("     python main.py pipeline --full --resume")
        click.echo("")
        click.echo("  2. 设置每日自动增量同步：")
        click.echo("     python main.py incremental")
```

**效果**:
- 新用户运行 `status` 时会看到清晰的操作指引
- 引导用户正确执行"第 1 步：全量同步"

---

## 用户旅程对比

### 变更前（可能的问题）

```
新用户 → 阅读文档 → 困惑：
  - "我应该先运行哪个命令？"
  - "全量和增量有什么区别？"
  - "每天都要运行全量同步吗？"
  → 可能错误地每日执行全量同步（浪费时间和 API 配额）
```

### 变更后（清晰的引导）

```
新用户 → 阅读 README → 看到"首次使用必读"表格
  → 点击链接 → 阅读 INITIALIZATION.md
  → 按照步骤执行：
     1. python main.py pipeline --full --resume（一次性）
     2. 设置 crontab 每日自动执行 incremental
  → 正确使用
```

---

## 技术细节

### 增量检测机制

系统使用 SQLite `sync_state` 表中的 `content_hash` 字段检测笔记变化：

```sql
CREATE TABLE sync_state (
    note_id TEXT PRIMARY KEY,
    content_hash TEXT,  -- ← 用于增量检测
    synced_at DATETIME,
    ...
);
```

**增量同步逻辑**:
```python
# 伪代码
for note in all_notes:
    current_hash = compute_hash(note.content)
    existing = db.get_note(note_id)
    
    if existing and existing['content_hash'] == current_hash:
        # 跳过未变化的笔记
        continue
    else:
        # 处理新增或修改的笔记
        process(note)
        db.insert_note(note_id, ..., content_hash=current_hash)
```

### 数据库存在性检查

```python
# main.py::incremental()
sync_db = Path(config.data_path) / "sync.db"
if not sync_db.exists():
    # 提示用户先执行全量同步
```

**为什么用数据库存在性作为标志？**
- 全量同步会创建 `sync_state` 表和初始记录
- 如果数据库不存在，说明从未执行过同步
- 简单可靠，不需要额外的状态文件

---

## 相关文档

- [INITIALIZATION.md](INITIALIZATION.md) - 新手指引（新增）
- [README.md](../README.md) - 项目概述（已更新）
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - Skills 使用（已更新）
- [USAGE.md](USAGE.md) - 使用指南（已更新）
- [KNOWLEDGE_PIPELINE.md](KNOWLEDGE_PIPELINE.md) - 完整管线说明
- [ARCHITECTURE_v5.md](ARCHITECTURE_v5.md) - v5.0 架构设计

---

## 总结

**核心变更**:
1. 新增 `INITIALIZATION.md` 新手指引文档
2. README/SKILLS_GUIDE/USAGE 三处文档强化"一次性全量 + 每日增量"概念
3. CLI 命令增加智能检测和友好提示

**预期效果**:
- 新用户不再混淆全量同步和增量同步
- 自动引导用户正确配置每日自动同步
- 减少因误操作导致的 API 配额浪费
