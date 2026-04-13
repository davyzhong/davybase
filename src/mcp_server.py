#!/usr/bin/env python3
"""
Davybase MCP Server

提供 AI Native 的知识生产线能力暴露：
- Tools: ingest_notes, digest_notes, compile_notes, publish_cards, get_pipeline_status
- Resources: davydb://status/ingest, davydb://status/digest, davydb://status/compile, davydb://status/publish
- Prompts: daily-report, error-analysis

Usage:
    python src/mcp_server.py

Configuration:
    Add to ~/.claude/settings.json:
    {
        "mcpServers": {
            "davybase": {
                "command": "python",
                "args": ["/Users/qiming/workspace/davybase/src/mcp_server.py"],
                "env": {}
            }
        }
    }
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from src.processing_status import (
    IngestStatus, DigestStatus, CompileStatus, PublishStatus,
    PipelineStatus, IngestRecord, DigestRecord, CompileRecord, PublishRecord
)
from src.config import Config

# 初始化 MCP 服务器 (使用 FastMCP)
mcp = FastMCP(
    name="davybase",
    instructions="Davybase 知识生产线 MCP 服务 - 提供笔记摄取、消化、编译、发布能力"
)

# 初始化配置和状态
config = Config()
state_dir = Path(config.vault_path) / ".davybase" / "progress"


# =============================================================================
# Tools - 可调用的能力
# =============================================================================

@mcp.tool()
async def ingest_notes(
    batch_size: int = 20,
    resume: bool = True,
    source: str = "getnote",
    concurrency: int = 3
) -> str:
    """从指定源抽取笔记到 raw/notes/_inbox/

    Args:
        batch_size: 单批次最大抽取数量 (默认：20)
        resume: 是否从中断处恢复 (默认：True)
        source: 数据来源 getnote|local|pdf (默认：getnote)
        concurrency: 并发请求数 (默认：3)

    Returns:
        JSON 格式的抽取结果
    """
    try:
        from src.orchestrator import IngestOrchestrator

        orchestrator = IngestOrchestrator(state_dir, config)
        result = await orchestrator.run(
            batch_size=batch_size,
            concurrency=concurrency,
            resume=resume,
            source=source
        )

        return json.dumps({
            "status": "completed",
            "total_extracted": result.get("total", 0),
            "failed": result.get("failed", 0),
            "duration_seconds": result.get("duration", 0)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "failed",
            "error": str(e),
            "suggestion": "建议减小 batch_size 或 concurrency 参数"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def digest_notes(
    inbox_dir: str = "raw/notes/_inbox/",
    apply: bool = False,
    limit: Optional[int] = None,
    provider: str = "minimax",
    provider_rotation: str = "round_robin",
    concurrency: int = 5
) -> str:
    """为散落笔记生成标题、分类、原子化拆解

    Args:
        inbox_dir: 待处理笔记目录 (默认：raw/notes/_inbox/)
        apply: 是否直接执行移动，否则预览 (默认：False)
        limit: 限制处理数量，测试用 (默认：null)
        provider: 首选 LLM 提供商 qwen|minimax|zhipu (默认：minimax)
        provider_rotation: LLM 分配策略 single|round_robin|weighted (默认：round_robin)
        concurrency: 并发任务数 (默认：5)

    Returns:
        JSON 格式的消化结果
    """
    try:
        from src.orchestrator import DigestOrchestrator

        orchestrator = DigestOrchestrator(state_dir, config)
        result = await orchestrator.run(
            inbox_dir=inbox_dir,
            apply=apply,
            limit=limit,
            provider=provider,
            provider_rotation=provider_rotation,
            concurrency=concurrency
        )

        return json.dumps({
            "status": "completed",
            "total_processed": result.get("total_processed", 0),
            "total_classified": result.get("total_classified", 0),
            "total_moved": result.get("total_moved", 0),
            "failed": result.get("failed", 0),
            "duration_seconds": result.get("duration", 0)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "failed",
            "error": str(e),
            "suggestion": "建议减小 concurrency 或切换 provider_rotation 为 single"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def compile_notes(
    kb_dir: str,
    threshold: int = 3,
    provider: str = "qwen",
    provider_rotation: str = "round_robin",
    concurrent_batches: int = 2
) -> str:
    """将知识库中的笔记聚合为结构化 Wiki 条目

    Args:
        kb_dir: 知识库目录 (如 processed/编程+AI/)
        threshold: 触发编译的最小笔记数 (默认：3)
        provider: 首选 LLM 提供商 qwen|minimax|zhipu (默认：qwen)
        provider_rotation: LLM 分配策略 single|round_robin|weighted (默认：round_robin)
        concurrent_batches: 同时编译的批次数量 (默认：2)

    Returns:
        JSON 格式的编译结果
    """
    try:
        from src.orchestrator import CompileOrchestrator

        orchestrator = CompileOrchestrator(state_dir, config)
        result = await orchestrator.run(
            kb_dir=kb_dir,
            threshold=threshold,
            provider=provider,
            provider_rotation=provider_rotation,
            concurrent_batches=concurrent_batches
        )

        return json.dumps({
            "status": "completed",
            "total_wiki_entries": result.get("total_wiki_entries", 0),
            "failed": result.get("failed", 0),
            "duration_seconds": result.get("duration", 0)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "failed",
            "error": str(e),
            "suggestion": "建议减小 concurrent_batches 或切换 provider_rotation"
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def publish_cards(
    wiki_title: str,
    template: str = "default"
) -> str:
    """基于 Wiki 条目生成 HTML 知识卡片

    Args:
        wiki_title: Wiki 标题
        template: 卡片模板 default|minimal|social (默认：default)

    Returns:
        JSON 格式的发布结果
    """
    # TODO: 实现实际的发布逻辑
    status = PublishStatus(state_dir)
    snapshot = status.snapshot()

    result = {
        "status": "ready",
        "message": f"发布服务就绪，已有 {snapshot['total_cards']} 张卡片",
        "wiki_title": wiki_title,
        "template": template,
        "progress_url": "davydb://status/publish"
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_pipeline_status() -> str:
    """获取完整管线状态快照

    Returns:
        JSON 格式的完整管线状态
    """
    pipeline = PipelineStatus(state_dir)
    snapshot = pipeline.snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_progress_text() -> str:
    """获取人类可读的进度文本

    Returns:
        格式化进度文本
    """
    pipeline = PipelineStatus(state_dir)
    return pipeline.format_progress()


# =============================================================================
# Resources - 可查询的状态资源
# =============================================================================

@mcp.resource("davydb://status/ingest")
async def ingest_status_resource() -> str:
    """摄取状态 - JSON 格式"""
    status = IngestStatus(state_dir)
    snapshot = status.snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@mcp.resource("davydb://status/digest")
async def digest_status_resource() -> str:
    """消化状态 - JSON 格式"""
    status = DigestStatus(state_dir)
    snapshot = status.snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@mcp.resource("davydb://status/compile")
async def compile_status_resource() -> str:
    """编译状态 - JSON 格式"""
    status = CompileStatus(state_dir)
    snapshot = status.snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@mcp.resource("davydb://status/publish")
async def publish_status_resource() -> str:
    """发布状态 - JSON 格式"""
    status = PublishStatus(state_dir)
    snapshot = status.snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@mcp.resource("davydb://progress/current")
async def current_progress_resource() -> str:
    """当前执行进度 - 文本格式"""
    pipeline = PipelineStatus(state_dir)
    return pipeline.format_progress()


# =============================================================================
# Prompts - 提示词模板
# =============================================================================

@mcp.prompt()
async def daily_report() -> str:
    """生成每日执行报告"""
    pipeline = PipelineStatus(state_dir)
    snapshot = pipeline.snapshot()

    template = f"""请基于以下管线状态生成一份执行报告：

## 当前管线状态

{json.dumps(snapshot, ensure_ascii=False, indent=2)}

## 报告格式要求

请生成以下格式的报告：

## 执行摘要
- 时间段：{datetime.now().strftime('%Y-%m-%d')}
- 关键指标摘要

## 各阶段详情

### 摄取阶段
- 已提取笔记数：{snapshot['ingest']['total_extracted']}
- 状态：{snapshot['ingest']['status']}

### 消化阶段
- 已处理：{snapshot['digest']['total_processed']}
- 已移动：{snapshot['digest']['total_moved']}
- 状态：{snapshot['digest']['status']}

### 编译阶段
- Wiki 条目数：{snapshot['compile']['total_wiki_entries']}
- 状态：{snapshot['compile']['status']}

### 发布阶段
- 卡片数：{snapshot['publish']['total_cards']}
- 状态：{snapshot['publish']['status']}

## 异常与建议
- 失败项：检查各阶段 status 是否为 failed
- 优化建议：基于数据提出改进建议
"""

    return template


@mcp.prompt()
async def error_analysis(error_logs: str) -> str:
    """错误分析助手

    Args:
        error_logs: 错误日志
    """
    template = f"""你是一个错误分析专家。请分析以下管线执行错误：

{error_logs}

请提供：
1. 根本原因分析 (Root Cause Analysis)
2. 短期修复建议 (Immediate Fix)
3. 长期预防措施 (Long-term Prevention)
4. 是否需要人工介入 (Yes/No)

请使用结构化的方式呈现分析结果。
"""

    return template


# =============================================================================
# 主函数 - 启动服务器
# =============================================================================

if __name__ == "__main__":
    # 启动 MCP 服务器 (stdio 模式)
    mcp.run()
