# 每日增量同步 get 笔记

从 get 笔记 API 增量抓取上次同步后的新笔记，保存为本地 Markdown 文件。

## 执行步骤

### 第 1 步：检查基准线状态

```bash
python -c "
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
    print('⚠️ 基准线未设置，请先执行全量同步: python main.py pipeline --full --resume')
s.close()
"
```

如果基准线未设置，提示用户先执行全量同步，**停止执行**。

### 第 2 步：执行增量抓取

```bash
cd /Users/qiming/workspace/davybase && python main.py ingest --incremental --batch-size 5 --concurrency 1
```

这个命令会：
1. 读取基准线时间戳（如 `2026-04-17 18:39:49`）
2. 遍历 9 个知识库，使用**早停策略**（第一页没有新笔记就跳过）
3. 遍历散落笔记，使用**早停策略**（遇到比基准线旧的笔记就停止分页）
4. 只抓取 `created_at > baseline` 的新笔记
5. 保存到 `/Users/qiming/ObsidianWiki/raw/notes/_inbox/`
6. 自动更新基准线为最新笔记的创建时间

### 第 3 步：汇报结果

从命令输出中提取：
- 新抓取笔记数量
- 失败数量
- 新基准线时间

向用户汇报。

## 配置信息

API 凭证存储在 `secrets.yaml` 中：

```yaml
getnote:
  api_key: "gk_live_460969336e637c74.7a6f130019958909917b011ae23f6aaca3b0a3994bbe93c4"
  client_id: "cli_c0483fe08869c9cf026b1063"
```

如果 `secrets.yaml` 不存在或缺少配置，提醒用户在 https://www.biji.com/openapi 的 "🔑 API Key" 页面获取。

## 预期耗时

- 知识库扫描（早停）：~10 分钟（9 个知识库 × 60 秒延迟）
- 散落笔记（早停）：~1 分钟（通常只读 1 页）
- 笔记详情抓取：每条约 60 秒

## 注意事项

- 如果长时间没有新笔记，散落笔记只需读 1 页就停止
- 基准线会在抓取完成后自动更新，无需手动操作
- 抓取的笔记保存为 Markdown 文件，带 frontmatter（note_id, created_at 等）
