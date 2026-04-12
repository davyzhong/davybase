# Davybase - AI Native 知识生产线

Davybase 是一个 AI Native 的知识管理系统，通过 MCP 协议和 Claude Skills 将 get 笔记中的原始内容转化为结构化 Wiki 知识。

## 快速开始

### 前提条件

1. 配置 get 笔记 API 凭据
2. 配置 LLM API 密钥（智谱/MiniMax）
3. 配置 MCP 服务器（见下方）

### 配置 MCP 服务器

编辑 `~/.claude/settings.json`：

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

### 使用 Skills

配置完成后，使用以下 Skills：

- `/davybase ingest` - 摄取笔记
- `/davybase digest` - 消化处理
- `/davybase compile` - 编译 Wiki
- `/davybase publish` - 发布卡片

## 目录结构

```
~/.claude/skills/obsidianSkills/
├── ingest/      - 摄取 Skill
├── digest/      - 消化 Skill
├── compile/     - 编译 Skill
└── publish/     - 发布 Skill
```

## MCP Tools

| Tool | 描述 |
|------|------|
| `ingest_notes` | 从 get 笔记 API 抽取笔记 |
| `digest_notes` | 生成标题、分类、原子化拆解 |
| `compile_notes` | 聚合笔记生成 Wiki |
| `publish_cards` | 生成 HTML 知识卡片 |
| `get_pipeline_status` | 获取完整管线状态 |
| `get_progress_text` | 获取人类可读进度 |

## MCP Resources

| Resource | 描述 |
|----------|------|
| `davydb://status/ingest` | 摄取状态 |
| `davydb://status/digest` | 消化状态 |
| `davydb://status/compile` | 编译状态 |
| `davydb://status/publish` | 发布状态 |
| `davydb://progress/current` | 当前进度文本 |

## MCP Prompts

| Prompt | 描述 |
|--------|------|
| `daily-report` | 生成每日执行报告 |
| `error-analysis` | 错误分析助手 |

## 完整文档

- [MCP Server 配置指南](../../davybase/docs/MCP_SERVER_GUIDE.md)
- [管线设计文档](../../davybase/docs/superpowers/specs/complete-pipeline-design.md)
- [迁移报告](../../davybase/docs/MIGRATION_REPORT.md)

## 定时任务

配置 Claude Cron 实现每日自动执行：

```bash
# 每天凌晨 3 点摄取
0 3 * * * claude "/davybase 摄取最近 100 条笔记"

# 每天凌晨 4 点消化
0 4 * * * claude "/davybase 消化 inbox 中的笔记"

# 每天凌晨 5 点编译
0 5 * * * claude "/davybase 编译达到阈值的知识库"
```

## 故障排查

### MCP 服务未响应

检查配置：
```bash
cat ~/.claude/settings.json | jq .mcpServers
```

测试服务：
```bash
python /Users/qiming/workspace/davybase/src/mcp_server.py
```

### Skills 未加载

检查目录：
```bash
ls -la ~/.claude/skills/obsidianSkills/
```
