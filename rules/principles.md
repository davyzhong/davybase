# Davybase 项目原则

本文档记录 Davybase 项目的设计和开发原则，用于指导后续开发决策。

---

## 一、知识库结构原则

详见 [knowledge-base-structure.md](knowledge-base-structure.md)

**核心约束：**
- 目录层级最多两级
- 一级目录 ≤ 20 个
- 二级目录 ≤ 10 个

---

## 二、API 设计与使用原则

### 1. 速率限制处理

**规则：** 所有外部 API 调用必须处理速率限制

```python
# 必须实现
- 指数退避重试（10s, 20s, 40s...）
- 检测 429 状态码并等待 Retry-After
- 批次间隔延迟（默认 3 秒）
- 请求间隔延迟（默认 1 秒）
```

**理由：** get 笔记 API 和 LLM API 都有严格的速率限制，不处理会导致批量处理失败。

### 2. 凭证管理

**规则：** API 密钥不得硬编码，必须通过以下方式配置：
- 优先级 1：环境变量
- 优先级 2：`secrets.yaml` 文件（已加入 `.gitignore`）

**理由：** 防止密钥泄露，支持多环境部署。

### 3. LLM 降级策略

**规则：** 关键 LLM 调用应有 fallback 方案

```
首选：智谱 GLM5
降级：MiniMax M2.7
最终：跳过并记录错误
```

**理由：** 单一 LLM 服务可能配额不足或暂时不可用。

---

## 三、数据处理原则

### 1. 状态追踪

**规则：** 所有异步/批量操作必须有状态追踪

```python
# 实现方式
- SQLite 数据库（sync.db）追踪同步状态
- JSON 进度文件（.processing_status.json）追踪处理状态
- 支持断点续传
```

**理由：** 批量处理可能中断，状态追踪避免重复处理和数据丢失。

### 2. 幂等性原则（避免重复操作）

**规则：** 所有操作在执行前必须检查是否已执行过

```python
# 抽取前检查
if note_id in extracted_ids:
    logger.info(f"跳过：{note_id} 已抽取")
    return

# 生成标题前检查
if note.get("summarized"):
    logger.info(f"跳过：{note_id} 已生成标题")
    return

# 分类前检查
if note.get("classified"):
    logger.info(f"跳过：{note_id} 已分类")
    return

# 移动前检查
if note.get("moved_to_kb"):
    logger.info(f"跳过：{note_id} 已移动到 {note['moved_to_kb']}")
    return
```

**检查方式：**
1. **文件标识** - 检查 Frontmatter 中的状态字段（`summarized`, `classified`, `moved_to_kb`）
2. **进度文件** - 检查 `.processing_status.json` 中的处理记录
3. **数据库** - 检查 `sync.db` 中的同步状态

**理由：**
- 避免浪费 API 配额和处理时间
- 支持安全的中断和恢复
- 用户可以反复运行脚本而不担心重复处理

**实现示例：**

```python
class ProcessingStatus:
    """处理状态管理器"""
    
    def is_extracted(self, note_id: str) -> bool:
        return note_id in self.extracted_ids
    
    def is_summarized(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("summarized", False)
    
    def is_classified(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("classified", False)
    
    def is_moved(self, note_id: str) -> bool:
        return self.status["notes"].get(note_id, {}).get("moved_to_kb") is not None

# 使用方式
async def process_note(note_id: str):
    if status.is_summarized(note_id):
        logger.info(f"跳过已处理的笔记：{note_id}")
        return
    
    # 执行实际处理...
```

### 3. 内容标识

**规则：** 自动生成的内容必须有明确标识

```markdown
<!-- 自动生成内容标识 -->
%%davybase-auto-begin%%
...自动生成的摘要...
%%davybase-auto-end%%

<!-- Frontmatter 标识 -->
summarized: true
summarized_at: '2026-04-13T06:15:20'
classified: true
moved_to_kb: '经营&管理'
```

**理由：** 
- 区分自动生成和手动编辑内容
- 支持增量更新（保留手动编辑）
- 追踪处理历史

### 4. 数据隔离

**规则：** 不同阶段的数据必须物理隔离

```
data/raw/        → 原始笔记暂存（.gitignore）
data/_inbox/     → 散落笔记暂存（.gitignore）
wiki/            → 编译后的 Wiki（.gitignore）
logs/            → 日志文件（.gitignore）
```

**理由：** 
- 原始数据不污染 Obsidian vault
- 敏感数据不提交到 Git
- 清晰的关注点分离

---

## 四、代码质量原则

### 1. 类型注解

**规则：** 所有函数签名必须有类型注解

```python
# 必须
async def compile_notes(notes: List[Dict]) -> WikiEntry:
    pass

# 禁止
async def compile_notes(notes):  # 无类型注解
    pass
```

**理由：** 提高代码可读性，支持静态类型检查。

### 2. 错误处理

**规则：** 所有外部调用必须有错误处理

```python
try:
    result = await api_call()
except httpx.HTTPStatusError as e:
    logger.error(f"API 错误：{e}")
    # 降级或重试
except Exception as e:
    logger.error(f"未知错误：{e}")
    # 记录并继续
```

**理由：** 批量处理中单个失败不应阻断整体流程。

### 3. 日志记录

**规则：** 关键操作必须有日志记录

```python
# 必须记录
- 批次开始/结束
- 成功/失败计数
- API 限流事件
- 文件移动操作

# 日志格式
'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

**理由：** 便于故障排查和进度跟踪。

### 4. 不可变模式

**规则：** 优先使用不可变对象

```python
# 推荐：返回新对象
def update_note(note: dict, updates: dict) -> dict:
    return {**note, **updates}

# 避免：原地修改
def update_note(note: dict, updates: dict):
    note.update(updates)  # 不推荐
```

**理由：** 不可变数据更安全，便于调试和并发处理。

---

## 五、用户交互原则

### 1. 预览模式

**规则：** 批量操作前必须支持预览

```bash
# 所有批量命令支持
--dry-run     # 预览模式
--sample N    # 预览样本数量
--limit N     # 限制处理数量
```

**理由：** 用户需要确认效果后再批量执行。

### 2. 确认机制

**规则：** 破坏性操作必须用户确认

```python
# 交互式确认
if not auto_confirm:
    confirm = input("是否继续？(y/n): ").strip().lower()
    if confirm != "y":
        print("操作已取消")
        return

# 或 --auto-confirm 跳过确认
parser.add_argument("--auto-confirm", action="store_true")
```

**理由：** 防止误操作导致数据丢失。

### 3. 进度反馈

**规则：** 长时间运行操作必须显示进度

```
批次 1/10 (本批 20 条)
  ✓ 成功：18 条
  ✗ 失败：2 条
  进度：20/200
```

**理由：** 用户需要知道处理状态，避免焦虑。

---

## 六、扩展性原则

### 1. 插件化设计

**规则：** 核心模块应支持插件化扩展

```python
# LLM 提供商
src/llm_providers/
├── base.py      # 抽象基类
├── zhipu.py     # 智谱
└── minimax.py   # MiniMax

# 添加新提供商只需：
# 1. 继承 LLMProvider 基类
# 2. 实现抽象方法
# 3. 在配置中注册
```

**理由：** 便于添加新的 LLM 提供商或输出格式。

### 2. 配置驱动

**规则：** 可变参数应通过配置控制

```yaml
# config.yaml
compiler:
  batch_size: 15      # 可调整
  max_retries: 2      # 可调整
  rate_limit_delay: 1.0  # 可调整
```

**理由：** 避免硬编码，便于调优。

---

## 七、安全原则

### 1. 输入验证

**规则：** 所有外部输入必须验证

```python
# 验证文件路径
def sanitize_filename(title: str) -> str:
    for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
        title = title.replace(char, "_")
    return title.strip()[:80]
```

**理由：** 防止路径注入和文件系统攻击。

### 2. 密钥脱敏

**规则：** 日志中 API 密钥必须脱敏

```python
# 显示前 20 字符
logger.info(f"API Key: {api_key[:20]}...")
```

**理由：** 防止日志泄露导致密钥暴露。

### 3. Git 安全

**规则：** 敏感文件必须加入 `.gitignore`

```
# .gitignore
data/raw/
data/_inbox/
data/sync.db
logs/
wiki/
secrets.yaml
.env
```

**理由：** 防止意外提交敏感数据。

---

## 八、性能原则

### 1. 批量优先

**规则：** 优先批量操作而非逐个处理

```python
# 推荐：批量处理
async def run_summarize(batch_size: int = 20):
    for i in range(0, len(notes), batch_size):
        batch = notes[i:i+batch_size]
        results = await asyncio.gather(*[process(n) for n in batch])

# 避免：逐个处理
for note in notes:
    await process(note)  # 太慢
```

**理由：** 批量并发显著减少总处理时间。

### 2. 并发控制

**规则：** 并发必须有上限控制

```python
semaphore = asyncio.Semaphore(3)  # 最多 3 个并发

async def process_with_semaphore(note):
    async with semaphore:
        return await process(note)
```

**理由：** 避免并发过高触发 API 限流。

---

## 附：原则检查清单

开发新功能时，对照以下清单检查：

- [ ] 是否遵守知识库结构约束（层级、数量）
- [ ] API 调用是否处理速率限制
- [ ] 敏感信息是否不硬编码
- [ ] 是否有状态追踪和断点续传
- [ ] **操作前是否检查重复（幂等性原则）**
- [ ] 自动生成内容是否有标识
- [ ] 错误是否有适当处理和日志
- [ ] 是否支持预览模式（--dry-run）
- [ ] 破坏性操作是否有确认机制
- [ ] 敏感文件是否加入 .gitignore
- [ ] 批量操作是否有并发控制

---

## 参考文档

- [knowledge-base-structure.md](knowledge-base-structure.md) - 知识库结构原则
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 系统架构
- [CONFIGURATION.md](docs/CONFIGURATION.md) - 配置指南
- [USAGE.md](docs/USAGE.md) - 使用指南
