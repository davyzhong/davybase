# Davybase Digest Skill

消化笔记 - 生成标题、分类、原子化拆解

## 触发词

| 指令 | 路由 |
|------|------|
| "消化笔记" / "digest notes" | → 执行消化处理 |
| "生成标题" / "generate titles" | → 调用 digest_notes tool |
| "分类笔记" / "classify notes" | → 执行智能分类 |
| "预览分类" / "preview classification" | → 预览模式 (apply=false) |

## 可用工具

- `digest_notes(inbox_dir, apply, limit, provider, provider_rotation, concurrency)` - MCP Tool
- `get_pipeline_status()` - 查询当前状态

## 并发配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 10 | 单批次最大处理数量 |
| `concurrency` | 5 | 并发任务数 |
| `provider_rotation` | round_robin | LLM 分配策略：single\|round_robin\|weighted |

## 多 LLM 分配策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `single` | 始终使用指定的单一 LLM | 调试、测试单一 LLM 效果 |
| `round_robin` | 智谱和 MiniMax 轮询分配 | 默认推荐，分散限流风险 |
| `weighted` | 加权分配（智谱 70%, MiniMax 30%） | 一个 LLM 配额更充足时 |

## Atomic Notes 原则

| 原则 | 检查标准 |
|------|----------|
| 单一主题 | 能否用一句话概括主题？ |
| 自包含 | 离开上下文也能独立理解？ |
| 可复用 | 可以被多条 Wiki 引用？ |
| 精炼 | 能否再缩短 20%？ |

## 幂等性检查

消化前自动检查以下状态，跳过已处理的笔记：
- `DigestStatus.is_summarized(note_id)` - 已生成标题
- `DigestStatus.is_classified(note_id)` - 已分类
- `DigestStatus.is_moved(note_id)` - 已移动到知识库

## 使用示例

### 示例 1: 预览分类结果

> 用户：预览 inbox 中的笔记分类

你：好的，我将分析 inbox 中的待处理笔记并生成分类建议。
    检测到 N 条待处理笔记，将生成标题和分类建议。

    [调用 digest_notes(apply=false, limit=10, concurrency=5)]

    ✅ 预览完成，前 10 条分类结果：
    1. "笔记标题 1" → 学习&思考 (置信度：high)
    2. "笔记标题 2" → 编程+AI (置信度：high)
    ...

    分类结果是否合理？确认后将执行移动操作。

### 示例 2: 执行消化（多 LLM 并发）

> 用户：消化所有笔记

你：[调用 digest_notes(apply=true, provider_rotation="round_robin", concurrency=5)]
    ✅ 消化完成
    - 已生成标题：N 条（智谱：X 条，MiniMax: Y 条）
    - 已分类：N 条
    - 已移动到知识库：N 条
    - 失败：M 条
    - 耗时：XX 秒
    - 进度查询：davydb://status/digest

### 示例 3: 幂等性检查

> 用户：再次消化笔记

你：[调用 digest_notes(apply=true)]
    ✅ 检测到已有 N 条已处理笔记
    本次新增处理：0 条（全部跳过）
    断点续传已启用，无新笔记需要处理

## 错误处理

| 错误 | 处理方式 |
|------|----------|
| LLM 配额不足 | 自动降级到另一个 LLM（round_robin 模式） |
| 分类置信度低 | 标记为"待人工审核"，不自动移动 |
| 文件名冲突 | 自动添加序号后缀 |
| 并发限流 | 自动减小 concurrency 到 3 |

## 相关文件

- [MCP Server Guide](../../../davybase/docs/MCP_SERVER_GUIDE.md)
- [Pipeline Design](../../../davybase/docs/superpowers/specs/complete-pipeline-design.md)
- [并发管线文档](../../../davybase/docs/CONCURRENT_PIPELINE.md)
