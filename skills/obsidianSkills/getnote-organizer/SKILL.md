# get 笔记整理助手

**Davybase 前半段 Skill - 知识收集与整理**

---

## 定位

每日增量收集 get 笔记，经过抽取→消化→分类三段式处理，最终归档到 16 个知识库目录。

**执行频率**: 每日自动运行（建议早上 6 点）  
**预期耗时**: 50-100 条笔记 ≈ 15-30 分钟  
**输出位置**: `processed/{16 分类}/`

---

## 触发词

| 指令 | 路由 |
|------|------|
| "从 get 笔记整理知识" | → 执行完整管线 |
| "运行知识入库" | → 执行完整管线 |
| "ingest notes from getnote" | → 执行完整管线 |
| "抽取 get 笔记" | → 仅执行 Ingest 阶段 |
| "消化笔记" | → 仅执行 Digest 阶段 |
| "分类笔记" | → 仅执行 Classify 阶段 |
| "查看知识入库状态" | → 查询状态 |

---

## 三段式处理流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  get 笔记整理助手                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │   Ingest     │ ──> │    Digest    │ ──> │  Classify    │             │
│  │   抽取       │     │    消化      │     │  二次分类    │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│        │                    │                    │                       │
│        ▼                    ▼                    ▼                       │
│  raw/notes/_inbox/    processed/{初步}/   processed/{16 分类}/           │
│  (原始 Markdown)     (带标题分类)        (最终归档位置)                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 可用工具

### MCP Tools

```python
# 阶段 1: Ingest
ingest_notes(
    batch_size: int = 20,
    resume: bool = True,
    source: str = "getnote",
    concurrency: int = 3
) -> str

# 阶段 2: Digest
digest_notes(
    inbox_dir: str = "raw/notes/_inbox/",
    apply: bool = True,
    limit: int = None,
    provider_rotation: str = "weighted",
    concurrency: int = 5
) -> str

# 阶段 3: Classify
classify_notes(
    source_dir: str = "raw/notes/_inbox/",
    apply: bool = True,
    limit: int = None,
    concurrency: int = 24
) -> str

# 状态查询
get_pipeline_status() -> dict
```

---

## 阶段 1: Ingest（抽取）

### 目标
从 get 笔记 API 抽取原始笔记

### 输入
- get 笔记 API 凭据（环境变量或 secrets.yaml）

### 输出
- `raw/notes/_inbox/{note_id}.md`

### 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 20 | 单批次最大抽取数量 |
| `concurrency` | 3 | 并发请求数 |
| `rate_limit_delay` | 60s | API 请求间隔（秒） |
| `resume` | true | 断点续传 |

### 幂等性检查
执行前自动检查：
- `IngestStatus.is_extracted(note_id)` - 已抽取的笔记跳过

### 使用示例

**用户**: 从 get 笔记整理知识

**助手**: 
```
好的，我将从 get 笔记 API 抽取原始笔记。

执行计划:
1. Ingest: 抽取原始笔记到 raw/notes/_inbox/
2. Digest: 生成标题、分类、标签
3. Classify: 二次分类校准到 16 个知识库

检测到约 100 条待处理笔记，预计耗时 15-30 分钟。
是否继续？(y/n)
```

**用户**: y

**助手**: [调用 ingest_notes(batch_size=20, resume=true, concurrency=3)]
```
✅ Ingest 完成
- 抽取：100 条
- 失败：0 条
- 耗时：42 秒
- 输出：raw/notes/_inbox/
```

---

## 阶段 2: Digest（消化）

### 目标
为原始笔记生成标题、分类、原子化拆解

### 输入
- `raw/notes/_inbox/*.md`

### 输出
- 带 frontmatter 的 Markdown：
  ```markdown
  ---
  title: 生成的标题
  category: 初步分类
  tags: [tag1, tag2, tag3]
  digest_at: 2026-04-17T07:10:00
  ---
  
  笔记内容...
  ```

### 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 10 | 单批次处理数量 |
| `concurrency` | 5 | 并发任务数 |
| `provider_rotation` | weighted | LLM 分配策略 |

### LLM 分配策略
| 策略 | 描述 | 权重 |
|------|------|------|
| `qwen` | 千问 Qwen | 45% |
| `minimax` | MiniMax M2.7 | 50% |
| `zhipu` | 智谱 GLM5 | 5% |

### 幂等性检查
执行前自动检查：
- `DigestStatus.is_summarized(note_id)` - 已生成标题的跳过
- `DigestStatus.is_classified(note_id)` - 已分类的跳过

### 使用示例

**用户**: 消化 inbox 中的笔记

**助手**: 
```
好的，我将为 inbox 中的笔记生成标题和分类。

执行计划:
- 使用千问和 MiniMax 轮询处理
- 并发度：5
- 预计耗时：5-10 分钟

是否继续？(y/n)
```

**用户**: y

**助手**: [调用 digest_notes(apply=true, concurrency=5)]
```
✅ Digest 完成
- 已生成标题：100 条（千问 45 条，MiniMax 50 条，智谱 5 条）
- 已分类：100 条
- 失败：0 条
- 耗时：6 分钟
```

---

## 阶段 3: Classify（二次分类）

### 目标
校准 Digest 阶段的初步分类，确保笔记归入正确的 16 分类知识库

### 为什么需要二次分类
- Digest 阶段使用简化的提示词，分类精度有限
- 部分笔记内容复杂，需要更详细的分类规则
- 16 分类体系需要更精确的判断逻辑

### 输入
- `raw/notes/_inbox/*.md` 或 `processed/{初步分类}/*.md`

### 输出
- 移动到正确的 `processed/{16 分类}/` 目录

### 16 分类体系

**新增知识库（6 个）**:
- AI 与编程：AI 编程工具（Claude Code/Cursor/n8n）、MCP 协议、开发范式
- 企业管理：业务管理、团队建设、组织变革、经营分析、领导力
- 财务与会计：财务报表、财务分析、管理会计、税务、审计
- 跨境物流：国际快递、面单系统、结算系统、供应链、物流业务架构
- 人文历史：历史典故、哲学思想、文化教育、国学经典
- 个人成长：人生感悟、学习方法、心理健康、职业发展

**现有知识库（10 个）**:
- 编程+AI、AI+ 机器学习、产品管理、系统架构、后端开发、前端开发、数据库、DevOps、经营&管理、学习&思考

### 分类规则
1. 优先使用新增的 6 个知识库（更精确）
2. 如果内容同时符合多个分类，选择最具体的那个
3. 技术实现细节 → 对应技术库
4. 业务/流程/架构 → 对应业务库
5. 个人感悟/通用知识 → 人文历史或个人成长

### 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `providers` | ["qwen-1", "qwen-2"] | 双千问实例 |
| `concurrency` | 12 | 每个实例并发数 |
| `batch_size` | 5 | 批次大小 |

### 幂等性检查
执行前自动检查：
- `ClassifyStatus.is_classified(note_id)` - 已分类的笔记跳过
- 检查笔记是否已在正确的分类目录

### 使用示例

**用户**: 对笔记进行二次分类

**助手**: 
```
好的，我将对笔记进行二次分类校准。

执行计划:
- 使用双千问实例并发处理
- 并发度：24（每个实例 12）
- 分类体系：16 个知识库
- 预计耗时：10-15 分钟

是否继续？(y/n)
```

**用户**: y

**助手**: [调用 classify_notes(apply=true, concurrency=24)]
```
✅ Classify 完成
- 分类：98 条成功，2 条失败（分类置信度低，待人工审核）
- 失败：2 条
- 耗时：12 分钟
- 输出：processed/{16 分类}/
```

---

## 完整执行流程

### 一键执行完整管线

**用户**: 从 get 笔记整理知识

**助手**: 
```
好的，我将执行 get 笔记整理助手完整管线。

执行计划:
┌─────────────────────────────────────────────────────────────┐
│  阶段 1: Ingest  →  阶段 2: Digest  →  阶段 3: Classify      │
│  (抽取)          (消化)           (二次分类)                │
│  raw/notes/      processed/       processed/{16 分类}/       │
└─────────────────────────────────────────────────────────────┘

检测到:
- 待抽取笔记：约 100 条
- 待消化笔记：约 100 条
- 待分类笔记：约 100 条

预计耗时：15-30 分钟
是否继续？(y/n)
```

**用户**: y

**助手**: 
```
[阶段 1: Ingest]
正在从 get 笔记 API 抽取...
✅ 完成：抽取 100 条，耗时 42 秒

[阶段 2: Digest]
正在生成标题和分类...
✅ 完成：消化 100 条，耗时 6 分钟
   - 千问：45 条
   - MiniMax: 50 条
   - 智谱：5 条

[阶段 3: Classify]
正在进行二次分类校准...
✅ 完成：分类 98 条，耗时 12 分钟
   - 成功：98 条
   - 失败：2 条（分类置信度低，待人工审核）

═══════════════════════════════════════════════════════════════
管线执行完成！

总计:
- 抽取：100 条
- 消化：100 条
- 分类：98 条
- 失败：2 条

输出位置:
- processed/AI 与编程/
- processed/企业管理/
- processed/个人成长/
- ... (共 16 个分类目录)

2 条失败笔记已标记为"待人工审核"，位于 processed/待审核/
```

---

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| **API 限流（429）** | 指数退避重试（10s, 20s, 40s, 60s, 60s） |
| **LLM 配额不足** | 自动降级到下一个 Provider |
| **JSON 解析失败** | 使用备用分类（"待审核"），标记待人工处理 |
| **网络超时** | 重试 3 次，仍失败则记录错误 |
| **分类置信度低** | 标记为"待人工审核"，不自动移动 |

---

## 状态查询

### 查询管线状态

**用户**: 查看知识入库状态

**助手**: [调用 get_pipeline_status()]
```
当前管线状态:

阶段 1: Ingest
- 已抽取：8645 条
- 最后运行：2026-04-17T06:00:00
- 状态：completed

阶段 2: Digest
- 已消化：8545 条
- 最后运行：2026-04-17T06:10:00
- 状态：completed

阶段 3: Classify
- 已分类：8447 条
- 最后运行：2026-04-17T06:25:00
- 状态：completed

待处理:
- 待抽取：约 100 条
- 待消化：0 条
- 待分类：0 条
```

---

## 配置示例

### config.yaml

```yaml
# 前半段：知识收集与整理
pipeline:
  ingest:
    enabled: true
    batch_size: 20
    concurrency: 3
    rate_limit_delay: 60.0
    resume: true

  digest:
    enabled: true
    batch_size: 10
    concurrency: 5
    provider_rotation: weighted

  classify:
    enabled: true
    providers: ["qwen-1", "qwen-2"]
    concurrency: 12
    batch_size: 5
```

### secrets.yaml

```yaml
# get 笔记 API 凭据
getnote:
  api_key: sk-xxx
  client_id: xxx

# LLM API 密钥
llm:
  qwen: sk-xxx
  minimax: sk-xxx
  zhipu: sk-xxx
```

---

## 相关文件

- [KNOWLEDGE_PIPELINE.md](../docs/KNOWLEDGE_PIPELINE.md) - 完整管线说明
- [MCP_SERVER_GUIDE.md](../docs/MCP_SERVER_GUIDE.md) - MCP 服务器配置
- [CONFIGURATION.md](../docs/CONFIGURATION.md) - 配置指南
