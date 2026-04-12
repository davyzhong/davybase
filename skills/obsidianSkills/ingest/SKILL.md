# Davybase Ingest Skill

摄取笔记到 `raw/notes/_inbox/`

## 触发词

| 指令 | 路由 |
|------|------|
| "摄取笔记" / "ingest notes" | → 执行笔记摄取 |
| "从 get 笔记抽取" / "extract from getnote" | → 调用 ingest_notes tool |
| "同步 get 笔记" / "sync getnote" | → 执行增量同步 |

## 可用工具

- `ingest_notes(batch_size, resume, source, concurrency)` - MCP Tool
- `get_pipeline_status()` - 查询当前状态

## 配置

确保 MCP 服务器已配置：

```json
{
  "mcpServers": {
    "davybase": {
      "command": "python",
      "args": ["/Users/qiming/workspace/davybase/src/mcp_server.py"]
    }
  }
}
```

## 并发配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 20 | 单批次最大抽取数量 |
| `concurrency` | 3 | 并发请求数 |
| `rate_limit_delay` | 1.0s | API 请求间隔 |

## 使用示例

### 示例 1: 摄取最近 100 条笔记

> 用户：摄取最近 100 条笔记

你：好的，我将从 get 笔记 API 抽取最近 100 条未处理的笔记。
    使用并发模式（concurrency=3），预计耗时约 2-3 分钟，是否继续？(y/n)

> 用户：y

你：[调用 ingest_notes(batch_size=100, resume=true, concurrency=3)]
    ✅ 完成：摄取服务就绪
    - 批次大小：100
    - 并发度：3
    - 断点续传：已启用
    - 进度查询：davydb://status/ingest

### 示例 2: 查看摄取状态

> 用户：现在摄取进度如何？

你：[调用 get_pipeline_status() 或查询 davydb://status/ingest]
    当前摄取状态：
    - 已提取：8545 条笔记
    - 状态：completed
    - 最后运行：2026-04-13T03:00:00

### 示例 3: 幂等性检查

> 用户：再次摄取笔记

你：[调用 ingest_notes(resume=true)]
    ✅ 检测到已有 8545 条已抽取笔记，已自动跳过
    本次新增抽取：0 条

## 错误处理

| 错误 | 处理方式 |
|------|----------|
| API 限流 | 自动等待 Retry-After 时间，建议减小 concurrency |
| 网络错误 | 自动重试 3 次，仍失败则建议检查网络连接 |
| 配额不足 | 建议联系 get 笔记管理员或切换到本地导入模式 |

## 相关文件

- [MCP Server Guide](../../../davybase/docs/MCP_SERVER_GUIDE.md)
- [Pipeline Design](../../../davybase/docs/superpowers/specs/complete-pipeline-design.md)
- [并发管线文档](../../../davybase/docs/CONCURRENT_PIPELINE.md)
