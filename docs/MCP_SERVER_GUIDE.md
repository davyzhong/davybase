# Davybase MCP Server 配置指南

## 快速开始

### 1. 安装 MCP SDK

```bash
pip install --system mcp
```

### 2. 配置 Claude MCP 服务器

编辑 `~/.claude/settings.json`，添加：

```json
{
  "mcpServers": {
    "davybase": {
      "command": "python",
      "args": ["/Users/qiming/workspace/davybase/src/mcp_server.py"],
      "env": {}
    }
  }
}
```

### 3. 重启 Claude Code

配置完成后，重启 Claude Code 以加载 MCP 服务器。

---

## 可用的 Tools

### `ingest_notes`

摄取笔记到 `raw/notes/_inbox/`

```python
# 使用示例
ingest_notes(batch_size=100, resume=True, source="getnote")
```

**参数**:
- `batch_size`: 单批次最大抽取数量 (默认：100)
- `resume`: 是否从中断处恢复 (默认：True)
- `source`: 数据来源 `getnote|local|pdf` (默认：getnote)

**返回**:
```json
{
  "status": "ready",
  "message": "摄取服务就绪，已提取 8545 条笔记",
  "batch_size": 100,
  "resume": true,
  "source": "getnote",
  "progress_url": "davydb://status/ingest"
}
```

---

### `digest_notes`

为散落笔记生成标题、分类、原子化拆解

```python
# 使用示例
digest_notes(inbox_dir="raw/notes/_inbox/", apply=False, limit=10, provider="minimax")
```

**参数**:
- `inbox_dir`: 待处理笔记目录 (默认：raw/notes/_inbox/)
- `apply`: 是否直接执行移动，否则仅预览 (默认：False)
- `limit`: 限制处理数量，测试用 (默认：null)
- `provider`: LLM 提供商 `zhipu|minimax` (默认：minimax)

**返回**:
```json
{
  "status": "ready",
  "message": "消化服务就绪，已处理 120 条，已移动 118 条",
  "inbox_dir": "/Users/qiming/ObsidianWiki/raw/notes/_inbox/",
  "apply": false,
  "provider": "minimax",
  "progress_url": "davydb://status/digest"
}
```

---

### `compile_notes`

将知识库中的笔记聚合为结构化 Wiki 条目

```python
# 使用示例
compile_notes(kb_dir="processed/编程+AI/", threshold=3, provider="zhipu")
```

**参数**:
- `kb_dir`: 知识库目录 (必需)
- `threshold`: 触发编译的最小笔记数 (默认：3)
- `provider`: LLM 提供商 `zhipu|minimax` (默认：zhipu)

**返回**:
```json
{
  "status": "ready",
  "message": "编译服务就绪，已有 25 个 Wiki 条目",
  "kb_dir": "/Users/qiming/ObsidianWiki/processed/编程+AI/",
  "threshold": 3,
  "provider": "zhipu",
  "progress_url": "davydb://status/compile"
}
```

---

### `publish_cards`

基于 Wiki 条目生成 HTML 知识卡片

```python
# 使用示例
publish_cards(wiki_title="反向传播算法", template="default")
```

**参数**:
- `wiki_title`: Wiki 标题 (必需)
- `template`: 卡片模板 `default|minimal|social` (默认：default)

**返回**:
```json
{
  "status": "ready",
  "message": "发布服务就绪，已有 5 张卡片",
  "wiki_title": "反向传播算法",
  "template": "default",
  "progress_url": "davydb://status/publish"
}
```

---

### `get_pipeline_status`

获取完整管线状态快照

```python
# 使用示例
get_pipeline_status()
```

**返回**:
```json
{
  "ingest": {
    "total_extracted": 8545,
    "last_run": "2026-04-13T10:30:00",
    "status": "completed"
  },
  "digest": {
    "total_processed": 120,
    "total_classified": 118,
    "total_moved": 115,
    "last_run": "2026-04-13T11:00:00",
    "status": "completed"
  },
  "compile": {
    "total_wiki_entries": 25,
    "last_run": "2026-04-13T12:00:00",
    "status": "completed"
  },
  "publish": {
    "total_cards": 5,
    "last_run": "2026-04-13T13:00:00",
    "status": "completed"
  },
  "generated_at": "2026-04-13T14:00:00"
}
```

---

### `get_progress_text`

获取人类可读的进度文本

```python
# 使用示例
get_progress_text()
```

**返回**:
```
Davybase 知识生产线状态
========================================
摄取阶段：8545 条笔记
消化阶段：120 条已处理，115 条已移动
编译阶段：25 个 Wiki 条目
发布阶段：5 张卡片
========================================
更新时间：2026-04-13T14:00:00
```

---

## Resources - 可查询的状态

### `davydb://status/ingest`

摄取状态 JSON 资源

### `davydb://status/digest`

消化状态 JSON 资源

### `davydb://status/compile`

编译状态 JSON 资源

### `davydb://status/publish`

发布状态 JSON 资源

### `davydb://progress/current`

当前执行进度文本资源

---

## Prompts - 提示词模板

### `daily-report`

生成每日执行报告

```python
# 使用示例
# 调用 daily-report prompt
```

### `error-analysis`

错误分析助手

```python
# 使用示例
# 调用 error-analysis prompt，传入错误日志
```

---

## 故障排查

### 1. MCP 服务器未启动

检查日志：
```bash
# 查看 MCP 服务器启动日志
tail -f ~/.claude/logs/mcp-davybase.log
```

### 2. Tools 无法调用

确认配置正确：
```bash
cat ~/.claude/settings.json | jq .mcpServers
```

### 3. 状态数据为空

检查状态目录：
```bash
ls -la /Users/qiming/ObsidianWiki/.davybase/progress/
```

---

## 开发调试

### 本地测试 MCP 服务器

```bash
# 直接运行服务器（stdio 模式）
python src/mcp_server.py

# 测试 Tools
python -c "
import asyncio
from src.mcp_server import ingest_notes

async def test():
    result = await ingest_notes(batch_size=10)
    print(result[0].text)

asyncio.run(test())
"
```

### 添加新的 Tool

```python
@server.tool("new_tool_name")
async def new_tool_name(param1: str, param2: int = 10) -> List[TextContent]:
    """工具描述

    Args:
        param1: 参数 1 说明
        param2: 参数 2 说明

    Returns:
        返回结果
    """
    # 实现逻辑
    result = {...}
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
```

---

## 最佳实践

1. **幂等性**: 所有 Tools 支持重复调用，内部检查状态避免重复处理
2. **断点续传**: 使用 `resume=True` 参数从中断处恢复
3. **预览模式**: 使用 `apply=False` 预览分类结果后再确认执行
4. **进度追踪**: 定期调用 `get_pipeline_status` 检查执行进度
5. **错误处理**: 失败时查看详细错误信息，使用 `error-analysis` prompt 分析

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Davybase 设计文档](docs/superpowers/specs/complete-pipeline-design.md)
