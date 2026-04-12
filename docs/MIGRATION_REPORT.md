# 目录迁移报告

**执行日期**: 2026-04-13  
**执行状态**: ✅ 完成

---

## 迁移前结构

```
/ObsidianWiki/
├── raw/                          # 混合了原始数据和已分类数据
│   ├── _inbox/                   # 散落笔记
│   ├── _failed/                  # 失败笔记
│   ├── 经营&管理/                 # 已分类知识库
│   ├── 学习&思考/                 # 已分类知识库
│   ├── 编程+AI/                   # 已分类知识库
│   ├── 未分类/                   # 未分类目录
│   ├── CN 遗产/                   # 未分类目录
│   └── ... (约 20 个目录)
├── wiki/                         # LLM 编译后的 Wiki
└── logs/
```

## 迁移后结构

```
/ObsidianWiki/
├── raw/                          # 原始文件库（只读）
│   ├── notes/                    # get 笔记原始导出
│   │   ├── _inbox/               # 散落笔记（未分类）
│   │   ├── _failed/              # 失败笔记
│   │   ├── CN 遗产/               # 按原始知识库分组
│   │   └── ... (未分类目录)
│   ├── documents/                # 文档类（PDF, Word 等）
│   ├── images/                   # 图片类
│   └── audio/                    # 录音类
│
├── processed/                    # ✨ 处理后的干净 Markdown
│   ├── _inbox/                   # 待处理（已加标题/分类标签）
│   ├── 经营&管理/                 # 已分类知识库
│   ├── 学习&思考/                 # 已分类知识库
│   ├── 编程+AI/                   # 已分类知识库
│   └── ID 记录/                   # 已分类知识库
│
├── wiki/                         # LLM 编译后的结构化 Wiki
├── cards/                        # HTML 知识卡片（预留）
├── logs/                         # 日志文件
└── .davybase/                    # ✨ 状态追踪数据
    ├── progress/                 # JSON 进度文件
    ├── sync.db                   # SQLite 数据库
    └── .processing_status.json   # 处理状态
```

---

## 迁移详情

### 1. 移动到 `processed/` 的目录

| 源路径 | 目标路径 | 状态 |
|--------|----------|------|
| `raw/经营&管理/` | `processed/经营&管理/` | ✅ |
| `raw/学习&思考/` | `processed/学习&思考/` | ✅ |
| `raw/编程+AI/` | `processed/编程+AI/` | ✅ |
| `raw/ID 记录/` | `processed/ID 记录/` | ✅ |

### 2. 移动到 `raw/notes/` 的目录

| 源路径 | 目标路径 | 状态 |
|--------|----------|------|
| `raw/_inbox/` | `raw/notes/_inbox/` | ✅ |
| `raw/_failed/` | `raw/notes/_failed/` | ✅ |
| `raw/CN 遗产/` | `raw/notes/CN 遗产/` | ✅ |
| `raw/SpringBoot 核心知识库/` | `raw/notes/SpringBoot 核心知识库/` | ✅ |
| `raw/ID 记录库/` | `raw/notes/ID 记录库/` | ✅ |
| `raw/未分类*` | `raw/notes/未分类*` | ✅ |
| `raw/通用*` | `raw/notes/通用*` | ✅ |
| `raw/企业架构/` | `raw/notes/企业架构/` | ✅ |
| `raw/宏观/` | `raw/notes/宏观/` | ✅ |
| `raw/未知分类/` | `raw/notes/未知分类/` | ✅ |
| `raw/人性的考验/` | `raw/notes/人性的考验/` | ✅ |
| `raw/极客/` | `raw/notes/极客/` | ✅ |
| `raw/户外运动/` | `raw/notes/户外运动/` | ✅ |

### 3. 移动到 `.davybase/` 的文件

| 源路径 | 目标路径 | 状态 |
|--------|----------|------|
| `raw/sync.db` | `.davybase/sync.db` | ✅ |
| `raw/.processing_status.json` | `.davybase/.processing_status.json` | ✅ |
| `raw/.inbox_extract_progress.json` | `.davybase/progress/.inbox_extract_progress.json` | ✅ |
| `raw/.sync.lock` | `.davybase/.sync.lock` | ✅ |
| `raw/check_files.py` | `.davybase/check_files.py` | ✅ |
| `raw/rename_remaining.py` | `.davybase/rename_remaining.py` | ✅ |

---

## 配置文件更新

### `config.yaml` 变更

```yaml
# 变更前
vault_path: /Users/qiming/ObsidianWiki
data_path: /Users/qiming/ObsidianWiki/raw
logs_path: /Users/qiming/ObsidianWiki/logs

# 变更后
vault_path: /Users/qiming/ObsidianWiki
data_path: /Users/qiming/ObsidianWiki/processed    # 处理后的干净 Markdown
raw_path: /Users/qiming/ObsidianWiki/raw           # 原始文件库（只读）
logs_path: /Users/qiming/ObsidianWiki/logs
state_path: /Users/qiming/ObsidianWiki/.davybase   # 状态追踪目录
```

---

## 数据统计

| 类别 | 数量 |
|------|------|
| 已分类知识库（processed/） | 5 个 |
| 散落笔记目录（raw/notes/） | ~15 个 |
| 媒体资源目录（raw/documents, images, audio） | 3 个 |
| 状态文件（.davybase/） | 5 个 |

---

## 后续行动

1. **Phase 2**: 实现状态追踪系统 (`src/processing_status.py`)
2. **Phase 3**: 开发 MCP Server (`src/mcp_server.py`)
3. **Phase 4-6**: 开发 Ingest/Digest/Compile Skills
4. **Phase 7**: 配置 Claude Cron 定时任务
5. **Phase 8**: 端到端测试和文档更新

---

**备注**: 目录迁移已完成，所有数据已按照新的三层架构（raw → processed → wiki）重新组织。
