# Davybase Compile Skill

编译 Wiki - 聚合笔记生成结构化 Wiki 条目

## 触发词

| 指令 | 路由 |
|------|------|
| "编译 Wiki" / "compile wiki" | → 执行编译 |
| "聚合笔记" / "aggregate notes" | → 调用 compile_notes tool |
| "生成双链" / "generate links" | → 编译并添加双向链接 |

## 可用工具

- `compile_notes(kb_dir, threshold, provider, provider_rotation, concurrent_batches)` - MCP Tool
- `get_pipeline_status()` - 查询当前状态

## 并发配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 15 | 单批次最大笔记数 |
| `concurrent_batches` | 2 | 同时编译的批次数量 |
| `provider_rotation` | round_robin | LLM 分配策略：single\|round_robin\|weighted |
| `threshold` | 3 | 触发编译的最小笔记数 |

## 多 LLM 分配策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `single` | 始终使用指定的单一 LLM | 调试、测试单一 LLM 效果 |
| `round_robin` | 智谱和 MiniMax 轮询分配 | **默认推荐**，分散限流风险 |
| `weighted` | 加权分配（智谱 70%, MiniMax 30%） | 一个 LLM 配额更充足时 |

## Wiki 条目结构

```markdown
---
title: 反向传播算法
source:
  - processed/编程 +AI/神经网络/reverse_prop.md
tags: [深度学习，神经网络，算法]
---

# 反向传播算法

%%davybase-auto-begin%%
## 核心摘要
...

## 关键概念
- [[梯度下降]]
- [[链式法则]]
%%davybase-auto-end%%
```

## 幂等性检查

编译前自动检查：
- `CompileStatus.is_processed(wiki_title)` - 已编译的 Wiki 条目跳过

## 使用示例

### 示例 1: 编译知识库（多 LLM 并发）

> 用户：编译编程 +AI 知识库

你：[调用 compile_notes(kb_dir="processed/编程+AI/", threshold=3, provider_rotation="round_robin", concurrent_batches=2)]
    ✅ 编译完成
    - 生成 Wiki 条目：N 个
    - LLM 分配：智谱 X 个批次，MiniMax Y 个批次
    - 耗时：XX 秒
    - 进度查询：davydb://status/compile

### 示例 2: 幂等性检查

> 用户：再次编译编程 +AI 知识库

你：[调用 compile_notes(kb_dir="processed/编程+AI/", threshold=3)]
    ✅ 检测到已有 N 个已编译 Wiki 条目
    本次新增编译：0 个（全部跳过）
    无新笔记需要处理

## 错误处理

| 错误 | 处理方式 |
|------|----------|
| LLM 配额不足 | 自动降级到另一个 LLM（round_robin 模式） |
| 笔记内容过短 | 跳过并记录，建议补充内容 |
| 主题聚类失败 | 使用默认分组策略 |
| 批次合并失败 | 保留中间结果，支持重新合并 |

## 相关文件

- [MCP Server Guide](../../../davybase/docs/MCP_SERVER_GUIDE.md)
- [Pipeline Design](../../../davybase/docs/superpowers/specs/complete-pipeline-design.md)
- [并发管线文档](../../../davybase/docs/CONCURRENT_PIPELINE.md)
