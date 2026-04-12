# Davybase Publish Skill

发布卡片 - 基于 Wiki 条目生成 HTML 知识卡片

## 触发词

| 指令 | 路由 |
|------|------|
| "发布卡片" / "publish cards" | → 执行发布 |
| "生成 HTML 卡片" / "generate HTML cards" | → 调用 publish_cards tool |
| "分享知识" / "share knowledge" | → 生成可分享的卡片 |

## 可用工具

- `publish_cards(wiki_title, template)` - MCP Tool
- `get_pipeline_status()` - 查询当前状态

## 卡片模板

| 模板 | 用途 |
|------|------|
| default | 标准知识卡片 |
| minimal | 简洁版本 |
| social | 社交媒体分享版 |

## 使用示例

> 用户：为"反向传播算法"生成卡片

你：[调用 publish_cards(wiki_title="反向传播算法", template="default")]
    ✅ 发布完成
    - 卡片路径：cards/2026-04-13/card_001.html
    - 进度查询：davydb://status/publish

## 相关文件

- [MCP Server Guide](../../../davybase/docs/MCP_SERVER_GUIDE.md)
