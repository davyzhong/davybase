# Davybase: 知识库 Wiki 管线设计

> get笔记 → Markdown → LLM编译 → Obsidian Wiki
> 灵感来源于 Karpathy 的个人知识库 wiki 方案。

## 问题定义

知识积累在 get笔记 中，被锁定在专有应用内。目标是构建自动化管线：抽取全部笔记、转换为 Markdown、通过 LLM 编译为带双向链接的结构化 wiki、最终发布到 Obsidian vault。支持全量导出 + 每日增量同步。

## 架构概览

```
get笔记 API
    |
    v
+-----------+    +-----------+    +-----------+    +---------+
| Extractor |--->| Converter |--->| Compiler  |--->| Writer  |
| (API拉取) |    |(markitdown)|    |(LLM编译)   |    |(Obsidian)|
+-----------+    +-----------+    +-----------+    +---------+
    |                                                |
    v                                                v
 data/raw/       同步状态 (SQLite)             /ObsidianWiki/
```

四个阶段，各司其职：

| 阶段 | 输入 | 输出 | 说明 |
|------|------|------|------|
| Extractor | get笔记 API | `data/raw/` 中的原始文件 | 按知识库拉取笔记，处理分页和附件下载 |
| Converter | `data/raw/` 中的 HTML/富文本 | 干净的 Markdown | 使用 markitdown 处理网页内容、图片等 |
| Compiler | 转换后的 Markdown | 结构化 wiki 条目 | LLM 提炼摘要、提取概念、生成双链 |
| Writer | 编译后的 wiki 条目 | Obsidian vault | 写入 MD 文件 + frontmatter + 标签 |

## 目录结构

**重要**：`data/raw/` 位于 davybase 项目目录内，**不在** Obsidian vault 中。这样原始笔记不会污染 Obsidian 的搜索、图谱和反向链接扫描。只有编译后的 `wiki/` 内容写入 vault。

```
davybase/                              # 项目目录
├── data/
│   ├── raw/                           # 原始笔记（暂存区）
│   │   ├── 知识库名A/
│   │   │   ├── {note_id}.md
│   │   │   └── attachments/
│   │   └── _inbox/                    # 不在任何知识库中的散落笔记
│   └── sync.db                        # SQLite 同步状态
├── src/
├── config.yaml
└── logs/

/Users/qiming/ObsidianWiki/            # Obsidian vault（独立）
├── wiki/                              # LLM 编译后的 wiki 条目
│   ├── 概念A.md
│   ├── 概念B.md
│   └── attachments/
├── templates/
└── .obsidian/
```

**data/raw/** 按知识库名称分文件夹。不在任何知识库中的笔记存入 `data/raw/_inbox/`。

**wiki/** 为扁平结构 —— 通过 `[[双链]]` 和 frontmatter 标签组织，不使用嵌套文件夹。

### Wiki 条目格式

```markdown
---
title: 反向传播算法
source:
  - data/raw/深度学习/note_12345.md
  - data/raw/深度学习/note_12346.md
tags: [深度学习, 神经网络, 算法]
created: 2026-04-11
updated: 2026-04-11
type: wiki
---

# 反向传播算法

%%davybase-auto-begin%%
## 核心摘要
（LLM 编译的内容）

## 关键概念
- [[梯度下降]]
- [[链式法则]]
- [[自动微分]]
%%davybase-auto-end%%

## 相关笔记
- [[Transformer模型]]
- [[注意力机制]]
```

自动生成的内容用 `%%davybase-auto-begin%%` / `%%davybase-auto-end%%` 注释块包裹。重新同步时，只替换标记之间的内容 —— 标记外的手动编辑内容会被保留。

每个 wiki 条目通过 `source` 字段记录原始笔记路径（相对于项目根目录），确保可溯源。

## 错误处理

每个管线阶段遵循统一的错误处理模式：

### 重试策略

| 错误类型 | 重试次数 | 退避策略 | 降级方案 |
|----------|----------|----------|----------|
| 网络超时 / 5xx | 3 | 指数退避（2s, 4s, 8s） | 记录日志并跳过，写入 `sync_state.error` |
| 限流（429 / 10202） | 1 | 等待 `retry-after` 头或 60s | 中止当前批次，下次运行时从游标恢复 |
| LLM 输出无效 | 2 | 无 | 记录原始响应，保存至 `data/raw/_failed/{note_id}.llm_raw.txt` |
| markitdown 转换失败 | 1 | 无 | 保存原始内容，标记 `conversion_failed: true` |
| SQLite 锁定 | 3 | 线性退避（1s） | 以错误退出码中止 |

### 死信处理

失败条目记录在 `sync_state.error` 字段，同时写入 `logs/dead_letter.log`。`status` 命令显示失败数量。手动重试：`python main.py retry-failed`。

### 并发保护

管线启动时创建锁文件 `data/.sync.lock`，内容为当前进程 PID。如果锁文件存在且 PID 存活，新运行立即中止。通过 atexit 处理器在完成或 SIGTERM/SIGINT 时释放锁。

### 日志

结构化日志同时输出到控制台和 `logs/sync.log`：

```
2026-04-11T06:00:01 INFO  davybase.extractor 开始全量同步
2026-04-11T06:00:03 INFO  davybase.extractor 获取知识库"深度学习"（45条笔记）
2026-04-11T06:00:15 WARN  davybase.extractor 触发限流，等待60秒
2026-04-11T06:01:15 INFO  davybase.extractor 恢复知识库"深度学习"分页
2026-04-11T06:05:00 ERROR davybase.compiler 批次 3/5 LLM 输出 YAML 无效，正在重试
```

日志级别：DEBUG（API 请求/响应体）、INFO（阶段进度）、WARN（重试、限流）、ERROR（阶段失败）。

## 阶段 1：Extractor（抽取器）

从 get笔记 API 拉取所有笔记和知识库内容到 `data/raw/`。

### 流程

```
1. GET /knowledge/list → 获取所有知识库
2. 遍历每个知识库：
   a. GET /knowledge/notes → 分页获取笔记（每页20条）
   b. 对每条笔记 GET /note/detail → 获取完整内容 + 附件
   c. 保存到 data/raw/{知识库名}/{note_id}.md
   d. 下载图片到 data/raw/{知识库名}/attachments/
3. GET /note/list → 获取不在任何知识库中的散落笔记
4. 保存到 data/raw/_inbox/{note_id}.md
```

### 笔记类型处理

| note_type | 处理方式 |
|-----------|----------|
| `plain_text` | 直接保存 `content` |
| `link` | 保存 `content` + `web_page.content`（原文）+ `web_page.url` |
| `img_text` | 保存 `content` + 下载图片附件 |
| `audio`/`meeting`/`local_audio`/`internal_record`/`class_audio`/`recorder_audio`/`recorder_flash_audio` | 保存 `content`（AI摘要）+ `audio.original`（转写原文） |
| 博主内容 | 保存 `post_media_text`（原文） |
| 直播内容 | 保存 `post_summary` + `post_media_text` |

### API 约束

- 笔记 ID 为 int64 —— Python 原生处理无精度问题。SQLite 中存储为 TEXT（int64 的字符串表示），与 API 保持一致。
- 每页固定 20 条，用 `has_more` / `next_cursor` 翻页
- 速率限制：请求间隔 >= 1 秒，避免触发 QPS 限流
- Base URL：`https://openapi.biji.com`
- 认证头：`Authorization: {api_key}`，`X-Client-ID: {client_id}`

### API 配置

API 凭据来自环境变量（与 getnote skill 保持一致）：
- `GETNOTE_API_KEY` — API Key（`gk_live_xxx`）
- `GETNOTE_CLIENT_ID` — Client ID（`cli_xxx`）

运行 `/note config` 完成 get 笔记配置后，这两个环境变量会自动设置。

LLM 凭据来自环境变量：`ZHIPU_API_KEY`、`MINIMAX_API_KEY`。

**安全**：所有密钥来自环境变量，永不写入源代码或配置文件。`config.yaml` 仅包含非敏感配置（路径、提供商名称、定时计划）。

## 阶段 2：Converter（转换器）

使用 Microsoft markitdown 库将 `data/raw/` 中的非 Markdown 内容转换为干净的 Markdown。

### 处理逻辑

- `plain_text` / `img_text` — `content` 已是 Markdown，直接透传
- `link` — `web_page.content` 可能是 HTML，用 markitdown 转换
- `audio`/`meeting` — `audio.original` 是纯文本转写，直接保存
- 图片 — 下载到 `data/raw/{知识库名}/attachments/`，Markdown 中图片路径替换为本地相对路径

## 阶段 3：Compiler（编译器）

使用 LLM 将原始笔记编译为结构化 wiki 条目。核心思路：**不是 1 条笔记 → 1 个 wiki 条目**，而是**多条相关笔记 → 聚合成一个概念条目**。这样 wiki 才有结构，不是原始笔记的翻版。

### 多 LLM 支持

两个提供商均已配置，均使用 OpenAI 兼容的 chat completions 协议：

```yaml
compiler:
  default_provider: zhipu
  providers:
    zhipu:
      name: 智谱 GLM5
      base_url: https://open.bigmodel.cn/api/paas/v4/chat/completions
      env_key: ZHIPU_API_KEY
      model: glm-5
    minimax:
      name: MiniMax M2.7
      base_url: https://api.minimaxi.com/v1/chat/completions
      env_key: MINIMAX_API_KEY
      model: codex-MiniMax-M2.7
```

统一接口：

```python
class LLMProvider:
    def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str: ...

class ZhipuProvider(LLMProvider): ...
class MiniMaxProvider(LLMProvider): ...
```

### 编译策略

1. 按知识库分组笔记（同知识库的笔记主题相近，便于聚类）
2. 将每个知识库的笔记送入 LLM 分析
3. LLM 识别核心概念，为每个概念创建 wiki 条目：
   - 核心摘要（200字以内）
   - 关键要点（要点列表）
   - 与其他概念的关系（使用 `[[双链]]`）
   - Frontmatter（title, source, tags, created, type）
4. 如果单个知识库笔记数 > 20，分批处理（每批 10-15 条）
5. 所有知识库编译完成后进行跨知识库去重

### 批次合并协议

当知识库有 >20 条笔记需多批次处理时：

1. **批次编译**：每批独立产出 wiki 条目
2. **合并遍历**：将所有批次输出送入单次 LLM 调用，附带指令：
   > "以下是从同一知识库不同批次编译的 wiki 条目。合并描述相同概念的条目。保留更丰富的摘要。合并关键要点，去除重复。更新双链指向合并后的条目标题。"
3. **输出**：该知识库去重后的 wiki 条目集合

### 跨知识库去重

所有知识库编译和批次合并完成后：

1. **标题匹配**：标题完全相同 → 合并（合并来源，保留更丰富的摘要）
2. **LLM 判断**：将所有 wiki 条目标题送入 LLM："以下哪些条目描述的是同一概念？返回应合并的标题对。"
3. **合并**：对每个匹配对，最后一次 LLM 调用合并两个条目（合并来源、合并摘要、去重要点、更新双链）

### LLM 提示词模板

```
你是一个知识库编辑。以下是从 get笔记 导出的原始笔记（Markdown 格式）。
请完成以下任务：

1. 阅读所有笔记，识别其中的核心概念和主题
2. 为每个核心概念创建一个 wiki 条目，包含：
   - 核心摘要（200字以内）
   - 关键要点（要点列表）
   - 与其他概念的关系（使用 [[双链]] 格式）
3. 每个条目必须包含 frontmatter（title, source, tags, created, type）
4. 使用 Obsidian Flavored Markdown 格式
5. 用 %%davybase-auto-begin%% 和 %%davybase-auto-end%% 标记包裹所有自动生成的内容

输出格式：每个 wiki 条目为一个文件，条目之间用 "---ENTRY---" 分隔

原始笔记：
{notes}

已有 wiki 条目（用于交叉引用）：
{existing_wiki}
```

## 阶段 4：Writer（写入器）

将编译后的 wiki 条目写入 Obsidian vault。

### 图片处理

- get笔记 返回远程图片 URL（OSS），需下载到本地
- 存储路径：`wiki/attachments/{note_id}_{filename}.png`
- Markdown 中的 `![](https://...)` 替换为 `![](attachments/xxx.png)`

### 冲突处理

内容哈希使用**原始笔记内容**（编译前）的 SHA-256，存储在 `sync_state.content_hash`。用于判断是否需要重新抽取和重新编译。

对 wiki 条目（编译输出）：

- 条目不存在 → 直接创建
- 条目已存在，`%%davybase-auto%%` 块内容未变 → 跳过
- 条目已存在，auto 块有变更 → 仅替换 `%%davybase-auto-begin%%` 和 `%%davybase-auto-end%%` 标记之间的内容。标记外的内容（手动编辑）予以保留。

## 同步状态（SQLite）

```sql
CREATE TABLE sync_state (
    note_id TEXT PRIMARY KEY,           -- int64 的字符串表示
    note_type TEXT,
    knowledge_base TEXT,
    raw_path TEXT,
    synced_at DATETIME,
    content_hash TEXT,                  -- 原始笔记内容的 SHA-256
    compiled_at DATETIME,
    wiki_path TEXT,
    error TEXT                          -- 最后一次错误信息，成功时为 NULL
);

CREATE TABLE sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT,                      -- 'full' 或 'incremental'
    provider TEXT,                      -- 'zhipu' 或 'minimax'
    started_at DATETIME,
    completed_at DATETIME,
    notes_extracted INTEGER,
    notes_compiled INTEGER,
    errors INTEGER
);

CREATE TABLE wiki_entries (
    title TEXT PRIMARY KEY,             -- wiki 条目标题（文件名安全）
    source_notes TEXT,                  -- note_id 的 JSON 数组
    wiki_hash TEXT,                     -- 编译内容（仅 auto 块）的 SHA-256
    created_at DATETIME,
    updated_at DATETIME
);
```

增量同步：仅拉取 `created_at` 或 `updated_at` 晚于上次同步时间的笔记。对比 `content_hash` 判断是否需要重新编译。

## CLI 命令

```bash
# 全量同步（抽取 + 转换 + 编译 + 写入）
python main.py full-sync [--provider zhipu|minimax]

# 增量同步（仅处理新增/变更的笔记）
python main.py incremental [--provider zhipu|minimax]

# 仅抽取，不编译（调试用）
python main.py extract-only

# 重新编译已有的 raw/（切换 LLM 或调优 prompt 时使用）
python main.py compile-only [--provider zhipu|minimax]

# 重试上次运行失败的项目
python main.py retry-failed

# 查看同步状态
python main.py status

# 检查 get笔记 API 配额
python main.py quota
```

### `status` 输出示例

```
上次同步: 2026-04-11 06:00:15 (增量, zhipu)
已同步笔记: 342
Wiki 条目: 89
失败: 2 (使用 'retry-failed' 重试)
Vault 大小: 12.3 MB
下次定时同步: 2026-04-12 06:00:00
```

### `quota` 命令

调用 `GET /open/api/v1/resource/quota`（通过 getnote CLI：`getnote quota -o json`），显示日/月 读/写配额限制和剩余次数。

## 定时同步

```bash
# 每天早上6点增量同步
0 6 * * * cd /Users/qiming/workspace/davybase && python main.py incremental >> logs/sync.log 2>&1
```

通过 `data/.sync.lock`（基于 PID）防止并发。锁文件存在且 PID 存活时，新运行立即中止。

## Skill 封装

将 Python CLI 封装为 Claude Code skill，支持自然语言调用。

### Skill 结构

```
~/.claude/skills/davybase/
├── SKILL.md              # Skill 定义（触发词、指令路由）
├── _meta.json
├── references/
│   ├── sync.md           # 同步命令详细说明
│   └── status.md         # 状态查询说明
└── scripts/
    └── davybase.py       # 封装层，调用主项目 CLI
```

### 触发词

```
"sync notes" / "同步笔记" / "sync to Obsidian"       -> python main.py incremental
"full export" / "全量导出" / "re-sync"               -> python main.py full-sync
"note status" / "笔记状态" / "how many synced"       -> python main.py status
"recompile" / "重新编译" / "compile with different model" -> python main.py compile-only --provider xxx
```

## 项目结构

```
davybase/
├── src/
│   ├── extractor.py       # get笔记 API 抽取
│   ├── converter.py       # markitdown 格式转换
│   ├── compiler.py        # LLM 编译（zhipu / minimax）
│   ├── writer.py          # 写入 Obsidian vault
│   ├── sync_state.py      # SQLite 同步状态管理
│   └── llm_providers/
│       ├── base.py         # LLMProvider 基类
│       ├── zhipu.py        # 智谱 GLM5
│       └── minimax.py      # MiniMax M2.7
├── data/
│   ├── raw/                # 原始笔记暂存区
│   └── sync.db             # SQLite 数据库
├── config.yaml
├── main.py                # CLI 入口
├── requirements.txt
├── logs/
├── tests/
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-11-knowledge-wiki-pipeline-design.md
```

## 依赖

- `markitdown>=0.1.0` — Microsoft 格式转 Markdown 工具
- `httpx>=0.27` — 异步 HTTP 客户端，用于 API 调用
- `sqlite3` — 标准库，同步状态跟踪
- `click>=8.0` — CLI 参数解析
- `pyyaml>=6.0` — 配置文件解析
- `hashlib` — 标准库，内容哈希用于变更检测

## 配置层级

| 来源 | 内容 | 示例 |
|------|------|------|
| `config.yaml` | 非敏感配置：路径、提供商名称、定时计划 | `vault_path`、`default_provider` |
| `~/.openclaw/openclaw.json` | get笔记 API 凭据 | `apiKey`、`GETNOTE_CLIENT_ID` |
| 环境变量 | LLM API 密钥 | `ZHIPU_API_KEY`、`MINIMAX_API_KEY` |

## API 配额与速率限制

- get笔记：遵守 QPS 限制（请求间隔 >= 1 秒）
- 智谱 GLM5：按账户速率限制
- MiniMax M2.7：按账户速率限制
- 所有 API 密钥存储在环境变量或外部配置文件中，永不写入源代码
