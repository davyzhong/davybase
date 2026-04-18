# 每日增量同步 get 笔记

> **注意**: 这是旧版 Skill 文档，新版已迁移至 `skills/01-collect.md`
>
> 从 get 笔记 API 增量抓取上次同步后的新笔记，保存为本地 Markdown 文件。

**适用平台**: Claude Code (`/daily-ingest`)、OpenClaw、Hermes 等任何支持执行 shell 命令的 AI 工具。

## 环境要求

- Python 3.13+
- 项目路径: `/Users/qiming/workspace/davybase`
- API 凭证已配置在 `secrets.yaml`:

```yaml
getnote:
  api_key: "gk_live_460969336e637c74.7a6f130019958909917b011ae23f6aaca3b0a3994bbe93c4"
  client_id: "cli_c0483fe08869c9cf026b1063"
```

## 执行步骤

### 第 1 步：检查基准线状态

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

如果输出包含 `ERROR`，提示用户先执行全量同步，**停止执行**。

### 第 2 步：执行增量抓取

```bash
cd /Users/qiming/workspace/davybase && python main.py ingest --incremental --batch-size 5 --concurrency 1
```

这个命令会：
1. 读取基准线时间戳（如 `2026-04-18 11:48:57`）
2. 遍历知识库，使用**早停策略**（每页检查时间戳，无新笔记立即跳过）
3. 遍历散落笔记，使用**早停策略**（遇到比基准线旧的笔记就停止分页）
4. 只抓取 `created_at > baseline` 的新笔记
5. 保存到 `/Users/qiming/ObsidianWiki/raw/notes/_inbox/` 为 Markdown 文件
6. 自动更新基准线

### 第 3 步：汇报结果

从命令输出中提取以下信息汇报给用户：
- 新抓取笔记数量
- 失败数量
- 新基准线时间
- 耗时

## 工作原理

```
get 笔记 API (note/list)     ──→  早停遍历（按时间倒序）
                                      │
                              遇到 created_at ≤ baseline → 停止
                                      │
                              只保留新笔记 → 逐条获取详情 → 保存为 .md
                                      │
                              自动更新 baseline 为最新笔记的 created_at
```

## 预期耗时

- 无新笔记：~30 秒（遍历 9 个知识库 + 散落笔记第一页）
- 5 条新笔记：~1-2 分钟
- 50 条新笔记：~5-10 分钟

## 注意事项

- 增量模式使用 2 秒限流延迟（非全量的 60 秒），请求量小不影响配额
- 每日配额 20,000 次，增量同步通常只需 15-20 次
- 基准线会在抓取完成后自动更新，无需手动操作
- 抓取的笔记保存为 Markdown 文件，带 frontmatter（note_id, source, created_at, extracted_at）
