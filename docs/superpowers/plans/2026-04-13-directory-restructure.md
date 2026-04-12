# Davybase 目录结构重构方案

## 当前问题分析

### 现状
```
/ObsidianWiki/
├── raw/                    # ❌ 混合了原始数据和已分类数据
│   ├── _inbox/            # 散落笔记（45MB，9350 条）
│   ├── _failed/           # 失败笔记
│   ├── 编程+AI/            # 已分类的知识库（7.2MB）← 不应该在这里
│   ├── 经营&管理/          # 已分类的知识库（576KB）← 不应该在这里
│   └── 各种未分类目录...
├── wiki/                  # LLM 编译后的 Wiki
└── logs/
```

### 问题
1. **raw/ 职责混乱** - 同时包含原始数据和已分类数据
2. **缺少 processed/ 层** - 没有"消化后"的中间层
3. **数据流不清晰** - 无法一眼看出哪些是原始数据，哪些已处理
4. **与原始架构不一致** - 原始设计 raw/ 应该是原始笔记暂存区（未经加工）

---

## 目标目录结构

```
/ObsidianWiki/
├── raw/                        # 原始文件库（只读，不直接编辑）
│   ├── documents/              # 文档类（PDF, Word, PPT 等）
│   ├── images/                 # 图片类
│   ├── web_pages/              # 网页存档
│   └── notes/                  # get 笔记原始导出（Markdown）
│       ├── _inbox/             # 散落笔记（未分类）
│       ├── 知识库 1/            # 按 get 笔记知识库分组
│       └── 知识库 2/
│
├── processed/                  # ✨ 新：处理后的干净 Markdown（主要工作区）
│   ├── _inbox/                 # 待处理的散落笔记（已加标题/分类标签）
│   ├── 经营&管理/               # 已分类的知识库目录
│   ├── 编程+AI/
│   └── ...
│
├── wiki/                       # LLM 编译后的结构化 Wiki 条目
│   ├── 反向传播算法.md
│   ├── Transformer 模型.md
│   └── ...
│
└── logs/                       # 日志文件
```

---

## 处理流程对应

| 阶段 | 输入 | 输出 | 存放位置 |
|------|------|------|----------|
| 1. 抽取 | get 笔记 API | 原始 Markdown | `raw/notes/` |
| 2. 标题/分类 | 原始 Markdown | 加标签的 Markdown | `processed/_inbox/` → `processed/{知识库}/` |
| 3. LLM 编译 | 处理后的 Markdown | 结构化 Wiki | `wiki/{title}.md` |

---

## 三阶段架构（参考项目设计）

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   摄取      │───>|   消化      │───>|   输出      │
│  (Ingest)   |    |  (Digest)   |    |  (Output)   |
└─────────────┘    └─────────────┘    └─────────────┘
     ↓                    ↓                    ↓
raw/notes/         processed/           wiki/
原始笔记            已分类 Markdown        结构化 Wiki
```

### 各阶段职责

#### 1. 摄取（Ingest）
- **目的**：接收外部原始资料，清洗和归拢到 raw 目录
- **关键设计**：按内容主题组织，不是按原材料对应关系
- **脚本**：`scripts/ingest.py`（原 `batch_extract_inbox.py` 重构）

#### 2. 消化（Digest）
- **目的**：将 raw 中的原始资料消化为原子化知识单元
- **关键设计**：
  - 遵循 Atomic Notes 原则
  - 支持一对多拆解（一条笔记 → 多篇原子文章）
  - 消化后的内容放到 processed/，**不再放回 raw/**
- **脚本**：`scripts/digest.py`（原 `note-summarizer` 重构）

#### 3. 输出（Output）
- **目的**：基于 processed/ 中沉淀的知识生成结构化 Wiki
- **关键设计**：
  - LLM 编译生成结构化条目
  - 可选：生成 HTML 知识卡片
- **脚本**：`src/compiler.py`（保持不变，输入路径改为 processed/）

---

## 迁移步骤

### Step 1: 创建新目录结构
```bash
mkdir -p /Users/qiming/ObsidianWiki/raw/notes
mkdir -p /Users/qiming/ObsidianWiki/processed/_inbox
mkdir -p /Users/qiming/ObsidianWiki/processed/{templates}
```

### Step 2: 移动现有数据
```bash
# 将当前 raw/ 下的所有内容移动到 raw/notes/
mv /Users/qiming/ObsidianWiki/raw/* /Users/qiming/ObsidianWiki/raw/notes/

# 将已分类的目录移动到 processed/
mv /Users/qiming/ObsidianWiki/raw/notes/经营\&管理 /Users/qiming/ObsidianWiki/processed/
mv /Users/qiming/ObsidianWiki/raw/notes/编程+AI /Users/qiming/ObsidianWiki/processed/
mv /Users/qiming/ObsidianWiki/raw/notes/学习\&思考 /Users/qiming/ObsidianWiki/processed/
```

### Step 3: 更新配置文件
```yaml
# config.yaml
vault_path: /Users/qiming/ObsidianWiki
data_path: /Users/qiming/ObsidianWiki/processed  # ← 改为 processed/
raw_path: /Users/qiming/ObsidianWiki/raw         # ← 新增
logs_path: /Users/qiming/ObsidianWiki/logs
```

### Step 4: 更新脚本路径引用
- `scripts/batch_extract_inbox.py` → `scripts/ingest.py`
  - 输出路径改为 `raw/notes/_inbox/`
  
- 创建 `scripts/digest.py`（新消化脚本）
  - 输入：`raw/notes/_inbox/`
  - 输出：`processed/_inbox/`（加标题和分类标签）

- `src/compiler.py`
  - 输入路径改为 `processed/`

---

## 脚本重构计划

### 1. `scripts/ingest.py`（摄取脚本）
```python
# 职责：从 get 笔记 API 抽取原始笔记到 raw/notes/
# 特点：
# - 不做任何分类，只按原始知识库分组
# - 支持断点续传
# - 幂等性：已存在的笔记跳过
```

### 2. `scripts/digest.py`（消化脚本）
```python
# 职责：为 raw/notes/ 中的笔记生成标题和分类
# 特点：
# - 遵循 Atomic Notes 原则
# - 支持一对多拆解
# - 输出到 processed/_inbox/ 或 processed/{知识库}/
# - 添加 Frontmatter 标识：summarized, classified, moved_to_kb
```

### 3. `scripts/apply_digest.py`（执行消化结果）
```python
# 职责：将 processed/_inbox/ 中的笔记移动到 processed/{知识库}/
# 特点：
# - 批量移动
# - 检查目录约束（一级≤20，二级≤10）
# - 幂等性：已移动的跳过
```

### 4. `src/compiler.py`（编译器）
```python
# 职责：将 processed/ 中的 Markdown 编译为 Wiki
# 修改：
# - 输入路径从 raw/ 改为 processed/
# - 保持不变
```

---

## Atomic Notes 原则定义

参考项目的设计，定义什么是"原子化笔记"：

| 原则 | 说明 | 检查标准 |
|------|------|----------|
| 单一主题 | 每条笔记只讲一个概念/想法 | 能否用一句话概括主题？ |
| 自包含 | 离开上下文也能独立理解 | 新读者能否看懂？ |
| 可复用 | 可以被多条 Wiki 引用 | 是否有通用价值？ |
| 精炼 | 简洁表达，不冗余 | 能否再缩短 20%？ |

---

## 迁移后的数据流

```
get 笔记 API
     │
     ▼
┌─────────────────┐
│  scripts/ingest │  ← 摄取阶段
└─────────────────┘
     │
     ▼
raw/notes/_inbox/     (原始笔记，未加工)
     │
     ▼
┌─────────────────┐
│ scripts/digest  │  ← 消化阶段
└─────────────────┘
     │
     ▼
processed/_inbox/   (已加标题和分类标签)
     │
     ▼
┌─────────────────┐
│scripts/apply_digest│
└─────────────────┘
     │
     ▼
processed/{知识库}/  (已分类)
     │
     ▼
┌─────────────────┐
│ src/compiler.py │  ← 输出阶段
└─────────────────┘
     │
     ▼
wiki/{title}.md     (结构化 Wiki)
```

---

## 迁移检查清单

- [ ] 创建新目录结构
- [ ] 移动现有数据
- [ ] 更新 config.yaml
- [ ] 更新 scripts/batch_extract_inbox.py（改名 ingest.py）
- [ ] 创建 scripts/digest.py（消化脚本）
- [ ] 创建 scripts/apply_digest.py（执行消化）
- [ ] 更新 src/compiler.py 输入路径
- [ ] 更新 README.md 目录结构说明
- [ ] 测试完整流程
- [ ] 清理旧目录

---

## 参考

- [principle.md](../rules/principles.md) - 项目原则
- [knowledge-base-structure.md](../rules/knowledge-base-structure.md) - 知识库结构约束
