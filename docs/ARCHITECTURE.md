# Davybase 架构文档

**版本**: v4.2  
**更新日期**: 2026-04-14

## 系统概述

Davybase 是一个知识库自动化管线，将 get 笔记 APP 中的笔记转换为 Obsidian Wiki 格式的结构化知识。

受 [Andrej Karpathy 的个人知识库方案](https://karpathy.ai/llmcookbook/) 启发，Davybase 解决的核心问题是：**如何将被困在笔记 APP 中的碎片化知识，自动化转换为可检索、可链接的结构化 Wiki**。

---

## 系统架构

### 四阶段管线

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Davybase 知识管线 (v4.2)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  阶段 1: 摄取              阶段 2: 消化             阶段 3: 编译          │
│  ┌─────────────┐         ┌─────────────────┐      ┌─────────────┐       │
│  │ Extractor   │  ────>  │ Digest          │      │ Compiler    │       │
│  │ (并发抽取)  │         │ Worker 池模式     │ ──> │ (并发编译)  │       │
│  └─────────────┘         │ - qwen Worker   │      └─────────────┘       │
│        │                 │ - zhipu Worker  │             │               │
│        │                 │ - minimax Worker│             │               │
│        v                 └─────────────────┘             v               │
│  raw/notes/_inbox/               │                   wiki/               │
│                                  v                                       │
│                          processed/{kb}/                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### v4.2 Worker 池模式架构

```
┌─────────────────────────────────────────────┐
│         任务队列 (asyncio.Queue)            │
│  [笔记 1] [笔记 2] ... [笔记 N]             │
└─────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Worker 1   │ │  Worker 2   │ │  Worker 3   │
│  千问       │ │  智谱       │ │  MiniMax    │
│  batch=2   │ │  batch=1   │ │  batch=2   │
│  delay=3s  │ │  delay=60s │ │  delay=3s  │
└─────────────┘ └─────────────┘ └─────────────┘
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ▼
              处理完立即领取下一批
```

**Worker 池模式特点**:
- 每个模型独立 Worker，真正的流水线作业
- 处理完立即领取下一批，无批次间等待
- Provider 级别限流控制，每个 API 独立延迟
- 实时进度追踪，显示每个模型的 ✓/✗ 计数
- 动态批次调整，根据处理速度自动优化

### 各阶段职责

| 阶段 | 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| **Extractor** | `src/extractor.py` | 从 get 笔记 API 抽取笔记 | API 凭据 | 原始 Markdown |
| **Converter** | `src/converter.py` | 格式标准化（markitdown） | HTML/富文本 | 标准 Markdown |
| **Digest** | `src/orchestrator.py` | 生成标题、分类、原子化拆解、移动 | 散落笔记 | 分类后的笔记 |
| **Compiler** | `src/compiler.py` | LLM 识别概念、聚合笔记 | 多条笔记 | Wiki 条目草稿 |
| **Writer** | `src/writer.py` | 写入 Obsidian，处理冲突 | Wiki 草稿 | 最终 .md 文件 |

---

## 数据流

### 完整同步流程

```
1. 用户运行：python main.py full-sync --provider zhipu
                    │
                    v
2. 加载配置：config.yaml + 环境变量
                    │
                    v
3. Extractor: 遍历 get 笔记知识库
   ├─ 获取知识库列表
   ├─ 逐个知识库获取笔记
   ├─ 保存为 data/raw/{kb_name}/note_{id}.md
   └─ 记录同步状态到 SQLite
                    │
                    v
4. Converter: 格式化笔记
   ├─ 解析 markitdown 输出
   ├─ 标准化 frontmatter
   └─ 清理格式问题
                    │
                    v
5. Compiler: LLM 编译
   ├─ 批量发送笔记给 LLM
   ├─ 识别核心概念和标签
   ├─ 生成双链 [[links]]
   └─ 聚合多条笔记为 Wiki 条目
                    │
                    v
6. Writer: 写入 Obsidian
   ├─ 检查目标文件是否存在
   ├─ 保留手动编辑内容
   ├─ 更新自动生成块
   └─ 写入 wiki/{title}.md
                    │
                    v
7. 完成：输出同步统计
```

### 增量同步流程

```
1. 读取 SQLite 同步状态
   ├─ 已同步笔记 ID 列表
   ├─ 最后同步时间
   └─ 各笔记 hash 值
                    │
2. 对比 API 返回的笔记列表
   ├─ 新增笔记 → 标记为 NEW
   ├─ 已修改笔记 → 标记为 MODIFIED
   └─ 未变化笔记 → 跳过
                    │
3. 仅处理 NEW + MODIFIED
   │
4. 更新 SQLite 状态
```

---

## 核心模块设计

### 1. Extractor（知识抽取）

**文件：** `src/extractor.py`

**关键函数：**
```python
class GetNoteClient:
    """get 笔记 API 客户端"""
    async def list_knowledge_bases() -> List[Dict]
    async def list_notes(kb_id: str) -> List[Dict]
    async def get_note_detail(note_id: str) -> Dict
    async def list_all_notes() -> List[Dict]  # 包括散落笔记

class Extractor:
    """知识抽取器"""
    async def run() -> Set[str]  # 返回已抽取的笔记 ID 集合
```

**设计要点：**
- 异步 HTTP 请求（httpx）
- 分页处理（游标分页）
- 速率限制处理（指数退避）
- 散落笔记支持（不在知识库中的笔记）

---

### 2. Compiler（LLM 编译）

**文件：** `src/compiler.py`

**关键函数：**
```python
class LLMProvider(ABC):
    """LLM 提供商基类"""
    async def compile_notes(notes: List[str]) -> WikiEntry
    
class ZhipuProvider(LLMProvider):
    """智谱 GLM5 实现"""
    
class MiniMaxProvider(LLMProvider):
    """MiniMax M2.7 实现"""

class Compiler:
    """编译器"""
    async def compile() -> List[WikiEntry]
```

**LLM Prompt 策略：**
```
输入：多条相关笔记
输出：
- 核心摘要（200-300 字）
- 关键概念列表（用于标签）
- 相关概念链接（用于双链）
- Wiki 条目结构
```

**降级策略：**
```
1. 尝试 Zhipu
2. 如果失败（配额不足/超时）→ 切换到 MiniMax
3. 如果仍然失败 → 跳过，记录错误
```

---

### 3. Writer（写入器）

**文件：** `src/writer.py`

**关键函数：**
```python
class Writer:
    """Obsidian 写入器"""
    async def write(entry: WikiEntry) -> bool
    
    def _preserve_manual_edit(old_content: str, new_content: str) -> str:
        """保留手动编辑内容"""
```

**冲突处理策略：**
```markdown
%%davybase-auto-begin%%
## 核心摘要
自动生成的摘要...
## 关键概念
- [[概念 1]]
- [[概念 2]]
%%davybase-auto-end%%

## 手动编辑部分
这部分内容不会被自动更新覆盖...
```

---

### 4. Sync State（同步状态管理）

**文件：** `src/sync_state.py`

**数据库结构：**
```sql
-- 同步状态表
CREATE TABLE sync_state (
    note_id TEXT PRIMARY KEY,
    kb_id TEXT,
    title TEXT,
    synced_at TIMESTAMP,
    content_hash TEXT,
    wiki_path TEXT
);

-- 知识库表
CREATE TABLE knowledge_base (
    kb_id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    last_sync TIMESTAMP
);
```

**用途：**
- 增量同步判断（对比 content_hash）
- 断点续传支持
- 同步历史追踪

---

## LLM 提供商接口

### 统一接口定义

```python
class LLMProvider(ABC):
    """LLM 提供商抽象基类"""
    
    @abstractmethod
    async def compile_notes(self, notes: List[Dict]) -> WikiEntry:
        """
        编译多条笔记为 Wiki 条目
        
        Args:
            notes: 笔记列表，每条包含 {title, content, tags}
        
        Returns:
            WikiEntry: {
                title: str,
                summary: str,
                concepts: List[str],
                links: List[str],
                tags: List[str]
            }
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """返回模型名称（用于日志）"""
        pass
```

### 提供商对比

| 特性 | 智谱 GLM5 | 千问 Qwen | MiniMax M2.7 |
|------|----------|-----------|-------------|
| 提供商 | 智谱 AI | 阿里云 | MiniMax |
| 模型 | `glm-5` | `qwen-plus` | `codex-MiniMax-M2.7` |
| 适用场景 | 通用编译 | 中文理解好 | 代码理解好 |
| 速率限制 | 严格 (TPM~100-200) | 宽松 | 宽松 |
| 请求间隔配置 | 60s | 3s | 3s |
|  fallback 优先级 | 降低至 5% | 45% | 50% |

**v4.2 限流缓解策略**:
- **加权轮询**: 智谱 5%、千问 45%、MiniMax 50%
- **Provider 级别延迟**: 每个 API 独立配置请求间隔
- **动态批次调整**: 触发限流时批次减半，连续成功时恢复

---

## 目录结构

```
davybase/
├── main.py                 # CLI 入口（click 命令定义）
├── config.yaml             # 应用配置
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量示例
│
├── src/
│   ├── __init__.py
│   ├── config.py           # 配置加载
│   ├── extractor.py        # get 笔记 API 抽取
│   ├── converter.py        # markitdown 格式转换
│   ├── compiler.py         # LLM 编译（多提供商）
│   ├── writer.py           # Obsidian 写入
│   ├── sync_state.py       # SQLite 状态管理
│   ├── processing_status.py # 状态追踪系统
│   ├── orchestrator.py     # 并发管线编排器 (v4.0/v4.2)
│   ├── utils.py            # 工具函数
│   └── llm_providers/
│       ├── __init__.py
│       ├── base.py         # LLMProvider 基类
│       ├── zhipu.py        # 智谱 GLM5
│       ├── minimax.py      # MiniMax M2.7
│       └── qwen.py         # 千问 Qwen
│
├── data/
│   ├── raw/                # 原始笔记暂存区（.gitignore）
│   └── sync.db             # SQLite 数据库（.gitignore）
│
├── wiki/                   # Obsidian Wiki 输出（.gitignore）
│
├── logs/                   # 日志文件（.gitignore）
│
├── tests/                  # 单元测试
│   ├── test_extractor.py
│   ├── test_compiler.py
│   └── test_writer.py
│
└── docs/
    ├── CONFIGURATION.md    # 配置指南
    ├── ARCHITECTURE.md     # 架构文档（本文件）
    ├── USAGE.md            # 使用指南
    ├── PIPELINE_CONFIG.md  # 管线配置详细指南
    ├── CONCURRENT_PIPELINE.md  # 并发管线设计文档
    ├── WORKER_POOL_IMPLEMENTATION.md  # Worker 池模式实施文档
    ├── RATE_LIMIT_TROUBLESHOOTING.md  # 限流故障排查
    └── superpowers/
        ├── specs/          # 设计文档
        └── plans/          # 实现计划
```

---

## 安全设计

### 敏感信息保护

```
┌────────────────────────────────────────────┐
│            敏感信息存储策略                 │
├────────────────────────────────────────────┤
│ ✅ 环境变量：API 密钥                        │
│ ✅ .gitignore: 排除 data/, logs/, wiki/   │
│ ✅ config.yaml: 不包含密钥                 │
│ ✅ 日志脱敏：API Key 显示前 20 字符           │
└────────────────────────────────────────────┘
```

### 数据隔离

- **原始笔记** (`data/raw/`)：不提交到 Git，不同步到 Obsidian
- **编译后 Wiki** (`wiki/`)：Obsidian 管理，不提交到 Git
- **同步状态** (`data/sync.db`)：本地 SQLite，不提交到 Git

---

## 扩展点

### 添加新的 LLM 提供商

1. 在 `src/llm_providers/` 创建新文件（如 `openai.py`）
2. 实现 `LLMProvider` 基类
3. 在 `config.yaml` 中添加配置
4. 在 `compiler.py` 中注册

```python
# src/llm_providers/openai.py
class OpenAIProvider(LLMProvider):
    async def compile_notes(self, notes: List[Dict]) -> WikiEntry:
        # 实现 OpenAI API 调用
        pass
```

### 添加新的输出格式

1. 创建新的 `Writer` 子类
2. 实现 `write()` 方法
3. 在 `main.py` 中添加 CLI 选项

---

## 性能考量

### 批量处理

- 默认 `batch_size: 15` 条笔记/批
- 避免单次请求过大（超 token 限制）
- 避免请求过频（触发 API 限流）

### 异步 IO

- 全链路异步（asyncio + httpx）
- 并发请求（受速率限制器控制）
- 非阻塞文件 IO

### 缓存策略

- SQLite 缓存同步状态
- 内容 hash 比对，跳过未变更
- 支持断点续传

### v4.2 Worker 池模式性能

**流水线作业**:
- 3 个 Worker 同时处理，无批次间等待
- 处理完立即领取下一批
- 50 条笔记预计耗时：5-8 分钟（批次模式 10-15 分钟）

**限流缓解**:
- Provider 级别延迟：智谱 60s，千问/MiniMax 3s
- 动态批次调整：触发限流时批次减半
- 加权轮询：智谱 5%、千问 45%、MiniMax 50%

**性能对比** (100 条笔记):
| 指标 | 串行模式 | 批次模式 (v4.0) | Worker 池模式 (v4.2) |
|------|----------|----------------|---------------------|
| 消化时间 | ~300 秒 | ~60 秒 | ~45 秒 |
| 智谱限流次数 | N/A | 5-10 次 | 0-2 次 |
| 总成功率 | ~85% | ~95% | ~98% |

---

## 相关文档

- [README.md](../README.md) - 项目概述
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南
- [USAGE.md](USAGE.md) - 使用指南
- [PIPELINE_CONFIG.md](PIPELINE_CONFIG.md) - 管线配置详细指南
- [CONCURRENT_PIPELINE.md](CONCURRENT_PIPELINE.md) - 并发管线设计文档
- [WORKER_POOL_IMPLEMENTATION.md](WORKER_POOL_IMPLEMENTATION.md) - Worker 池模式实施文档
- [RATE_LIMIT_TROUBLESHOOTING.md](RATE_LIMIT_TROUBLESHOOTING.md) - 限流故障排查
