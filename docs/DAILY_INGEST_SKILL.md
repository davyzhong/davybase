# Skill: 每日增量同步 get 笔记

> **注意**: 这是旧版通用 Skill 文档，新版已迁移至 `skills/01-collect.md`
>
> 从 get 笔记 API 增量抓取上次同步后的新笔记，保存为本地 Markdown 文件。
>
> **适用平台**: Claude Code、OpenClaw、Hermes 等任何支持执行 shell 命令的 AI 工具。
>
> **版本**: v5.2 | **更新日期**: 2026-04-18

---

## 触发词

- "执行增量同步"
- "抓取 get 笔记新增笔记"
- "daily ingest"
- "从 get 笔记整理知识"

---

## 环境配置

### 项目路径

```
/Users/qiming/workspace/davybase
```

### API 凭证

已配置在 `secrets.yaml` 中：

| 配置项 | 值 |
|--------|-----|
| API Key | `gk_live_460969336e637c74.7a6f130019958909917b011ae23f6aaca3b0a3994bbe93c4` |
| Client ID | `cli_c0483fe08869c9cf026b1063` |

如果缺少配置，提醒用户访问 https://www.biji.com/openapi 的 "🔑 API Key" 页面获取。

---

## 执行流程

### 第 1 步：检查基准线

```bash
cd /Users/qiming/workspace/davybase && python -c "
from src.sync_state import SyncState
from src.config import Config
config = Config()
db_path = f'{config.vault_path}/.davybase/sync_state.db'
s = SyncState(db_path)
ts = s.get_last_sync_timestamp()
t = s.get_last_sync_type()
if ts:
    print(f'基准线: {ts} ({t})')
else:
    print('ERROR: 基准线未设置，请先执行全量同步: python main.py pipeline --full --resume')
s.close()
"
```

- 如果输出 `基准线: 2026-04-18 11:48:57 (incremental)` → 继续第 2 步
- 如果输出 `ERROR` → 提示用户先执行全量同步，**停止执行**

### 第 2 步：执行增量抓取

```bash
cd /Users/qiming/workspace/davybase && python main.py ingest --incremental --batch-size 5 --concurrency 1
```

### 第 3 步：汇报结果

从命令输出中提取：
- 新抓取笔记数量
- 失败数量
- 新基准线时间
- 耗时

向用户汇报。

---

## 工作原理

```
┌─────────────────────────────────────────────────────────────────────┐
│  增量同步流程（早停策略）                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 读取基准线：last_sync_at（如 2026-04-18 11:48:57）             │
│                                                                     │
│  2. 遍历知识库（9 个）：                                             │
│     每页检查 created_at > baseline？                                 │
│     → 否：早停，跳到下一个知识库                                     │
│     → 是：保留该笔记                                                │
│                                                                     │
│  3. 遍历散落笔记（API 按时间倒序）：                                 │
│     遇到 created_at ≤ baseline → 停止分页                           │
│     只获取基准线之后的新笔记                                         │
│                                                                     │
│  4. 逐条获取新笔记详情 → 保存为 Markdown → 更新基准线               │
│                                                                     │
│  【基准线逻辑】                                                      │
│  - 基准线 = 最新抓取笔记的 created_at（API 返回的笔记创建时间）        │
│  - 如果抓到 0 条，基准线不更新（避免遗漏中间笔记）                     │
│  - 增量同步只抓取 created_at > baseline 的笔记                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 预期耗时

| 场景 | 耗时 |
|------|------|
| 无新笔记 | ~30 秒 |
| 5 条新笔记 | ~1-2 分钟 |
| 50 条新笔记 | ~5-10 分钟 |

---

## API 配额

| 项目 | 数值 |
|------|------|
| 每日配额 | 20,000 次 |
| 增量同步用量 | ~15-20 次 |
| 当前已用 | ~1,200 次 |

配额充足，增量同步不影响正常使用。

---

## 输出格式

笔记保存到 `/Users/qiming/ObsidianWiki/raw/notes/_inbox/`，格式：

```markdown
---
note_id: 1907471846405374992
source: getnote
created_at: 2026-04-18 08:19:51
extracted_at: 2026-04-18T11:48:30.123456
---

（笔记正文内容）
```

---

## 故障排查

| 问题 | 解决方案 |
|------|---------|
| 401 Unauthorized | 检查 secrets.yaml 中的 API Key 是否过期 |
| 基准线未设置 | 先执行 `python main.py pipeline --full --resume` |
| 触发限流 (429) | 系统自动重试，无需干预 |
| 笔记无内容 | 图片/语音/ref 类型笔记，API 不返回文本内容，属正常情况 |

---

## 相关文件

- Skill 文件: `.claude/commands/daily-ingest.md`
- 配置文件: `secrets.yaml`、`config.yaml`
- 基准线存储: `/Users/qiming/ObsidianWiki/.davybase/sync_state.db`
- 进度文件: `/Users/qiming/ObsidianWiki/.davybase/progress/.inbox_extract_progress.json`
- 技术文档: `docs/INCREMENTAL_SYNC.md`
