# Davybase 初始化指南

**版本**: v5.0  
**适用对象**: 首次使用 Davybase 的新用户

---

## 核心工作流：一次性全量 + 每日增量

Davybase 的设计基于以下工作流：

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

**重要**：
- ✅ **全量同步只需执行一次** —— 除非你需要完全重建知识库
- ✅ **增量同步每日执行** —— 这是日常使用的主要方式
- ✅ **系统自动检测变化** —— 不会重复处理已有笔记

---

## 第 1 步：全量同步（一次性）

### 什么是全量同步？

全量同步会：
1. 从 get 笔记 API 抽取**所有历史笔记**
2. 经过三段式处理（抽取→消化→分类）
3. 编译为 Wiki 条目
4. 发布到 Obsidian

### 什么时候执行？

- ✅ **首次使用 Davybase 时**（必须执行）
- ✅ 需要完全重建知识库时（极少情况）
- ❌ **不要**每日执行（会浪费时间和 API 配额）

### 执行方式

#### 方式 1: 使用 AI Native Skills（推荐）

```bash
# 1. 配置 MCP 服务器（见 MCP_SERVER_GUIDE.md）

# 2. 在 Claude 中触发
/getnote-organizer     # 执行前半段：知识收集与整理
/wiki-creator          # 执行后半段：知识创作与输出
```

#### 方式 2: 使用 CLI 命令

```bash
# 一键执行完整管线
python main.py pipeline --full --resume

# 或者分阶段执行
python main.py ingest --batch-size 20 --concurrency 3 --resume
python main.py digest --apply
python main.py compile --kb-dir processed/ --concurrent-batches 2
```

### 预计耗时

| 笔记数量 | 预计耗时 |
|---------|---------|
| 100 条 | 15-30 分钟 |
| 500 条 | 1-2 小时 |
| 1000 条 | 2-4 小时 |
| 5000+ 条 | 8-12 小时 |

### 执行后检查

```bash
# 查看同步状态
python main.py status

# 预期输出示例：
# 上次同步：2026-04-17T10:00:00 (full, qwen)
# 已同步笔记：8645
# Wiki 条目：150
# 失败：0
```

---

## 第 2 步：增量同步（每日自动）

### 什么是增量同步？

增量同步会：
1. 自动检测**新增或修改**的笔记
2. 仅处理这些笔记
3. **跳过**未变化的笔记（通过 `content_hash` 比对）
4. 追加到已有知识库

### 为什么需要每日执行？

- 📝 get 笔记是日常记录工具，每天会产生新内容
- 🔄 每日同步保持知识库新鲜
- ⚡ 增量处理速度快（通常 5-10 分钟）

### 执行方式

#### 方式 1: 手动执行（测试用）

```bash
# 增量同步
python main.py incremental
```

#### 方式 2: 定时任务（推荐 - 生产环境）

**macOS/Linux (crontab)**:

```bash
# 编辑 crontab
crontab -e

# 添加以下内容（每天早上 6 点自动执行）
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py incremental >> logs/incremental.log 2>&1
```

**Windows (任务计划程序)**:

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器：每天 6:00
4. 设置操作：启动程序 `python.exe`，参数 `main.py incremental`

#### 方式 3: AI Native Skills 定时执行

在 Claude 中配置定时 Skills 执行（见 [CRON_SETUP.md](CRON_SETUP.md)）。

### 增量同步如何工作？

```
┌─────────────────────────────────────────────────────────────┐
│  增量同步流程                                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 读取 SQLite 状态数据库                                   │
│     └─> 记录每条笔记的 content_hash                          │
│                                                             │
│  2. 从 get 笔记 API 获取笔记列表                             │
│     └─> 比对本地 hash                                        │
│         ├─ hash 相同 → 跳过（未变化）                        │
│         └─ hash 不同 → 处理（新增/修改）                     │
│                                                             │
│  3. 仅处理变化的笔记                                         │
│     └─> 节省时间和 API 配额                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 预计耗时

| 新增笔记 | 预计耗时 |
|---------|---------|
| 5 条 | 1-2 分钟 |
| 20 条 | 5-8 分钟 |
| 50 条 | 10-15 分钟 |
| 100 条 | 15-30 分钟 |

---

## 配置每日自动同步

### 步骤 1: 确认全量同步已完成

```bash
# 检查是否已有同步记录
python main.py status
```

如果输出显示已有同步记录（如"已同步笔记：8645"），说明全量同步已完成。

### 步骤 2: 测试增量同步

```bash
# 手动运行一次增量同步，确认正常
python main.py incremental
```

### 步骤 3: 设置定时任务

选择以下一种方式：

**A. crontab（推荐 macOS/Linux）**:
```bash
crontab -e
# 添加：
0 6 * * * cd /Users/qiming/workspace/davybase && /usr/bin/python3 main.py incremental >> logs/incremental.log 2>&1
```

**B. launchd（macOS 系统级）**:
```xml
<!-- ~/Library/LaunchAgents/com.davybase.incremental.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.davybase.incremental</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/qiming/workspace/davybase/main.py</string>
        <string>incremental</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/qiming/workspace/davybase</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
```

```bash
# 加载任务
launchctl load ~/Library/LaunchAgents/com.davybase.incremental.plist
```

**C. Windows 任务计划程序**:
1. 打开"任务计划程序库"
2. "创建基本任务"
3. 名称：Davybase Incremental Sync
4. 触发器：每天 6:00
5. 操作：启动程序
   - 程序：`C:\Path\To\python.exe`
   - 参数：`main.py incremental`
   - 起始于：`C:\Path\To\davybase`

### 步骤 4: 验证定时任务

```bash
# crontab 验证
crontab -l

# launchd 验证
launchctl list | grep davybase

# Windows 验证
# 在任务计划程序中查看任务状态
```

---

## 常见问题

### Q: 我不小心执行了两次全量同步，会有问题吗？

**A**: 不会有数据问题，但会浪费时间和 API 配额。系统使用 `content_hash` 比对，重复内容不会被重复处理。

### Q: 如何确认增量同步真的在增量（而不是全量）？

**A**: 查看日志文件：
```bash
tail -f logs/incremental.log
```
如果看到"跳过 XXX 条已处理笔记"，说明是增量同步。

### Q: 全量同步后多久可以开始增量同步？

**A**: **立即可以**。全量同步完成后，下一次就可以执行增量同步。

### Q: 如果我想完全重建知识库怎么办？

**A**: 
```bash
# 1. 删除状态数据库
rm data/sync.db

# 2. 重新执行全量同步
python main.py pipeline --full --resume
```

### Q: 增量同步失败了怎么办？

**A**: 
1. 查看日志：`tail logs/incremental.log`
2. 使用 `--resume` 参数重试：`python main.py incremental --resume`
3. 检查 API 配额和密钥是否有效

---

## 最佳实践

### 1. 首次同步前先测试

```bash
# 用小批量测试配置
python main.py pipeline --full --resume --limit 5

# 确认正常后执行全量
python main.py pipeline --full --resume
```

### 2. 监控每日同步

```bash
# 设置邮件或通知（可选）
# 在 crontab 中添加：
0 7 * * * cat /Users/qiming/workspace/davybase/logs/incremental.log | mail -s "Davybase Sync Report" your@email.com
```

### 3. 定期清理日志

```bash
# 每月清理一次日志（避免占用过多空间）
find logs/ -name "*.log" -mtime +30 -delete
```

### 4. 备份状态数据库

```bash
# 每周备份一次状态
cp data/sync.db data/sync.db.backup.$(date +%Y%m%d)
```

---

## 相关文档

- [README.md](../README.md) - 项目概述和快速开始
- [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - Skills 使用指南
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南
- [CRON_SETUP.md](CRON_SETUP.md) - 定时任务配置详解
- [FAQ.md](FAQ.md) - 常见问题解答
