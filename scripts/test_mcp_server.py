#!/usr/bin/env python3
"""
测试 MCP Server Tools

运行此脚本测试所有 MCP Tools 是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp_server import (
    ingest_notes,
    digest_notes,
    compile_notes,
    publish_cards,
    get_pipeline_status,
    get_progress_text,
    ingest_status_resource,
    digest_status_resource,
    compile_status_resource,
    publish_status_resource,
    current_progress_resource,
    daily_report,
)


async def test_tools():
    """测试所有 Tools"""
    print("=" * 60)
    print("Davybase MCP Server Tools 测试")
    print("=" * 60)

    # 测试 ingest_notes
    print("\n1. 测试 ingest_notes...")
    result = await ingest_notes(batch_size=50, resume=True)
    print(f"   ✓ 返回：{result[:100]}...")

    # 测试 digest_notes
    print("\n2. 测试 digest_notes...")
    result = await digest_notes(apply=False, limit=5)
    print(f"   ✓ 返回：{result[:100]}...")

    # 测试 compile_notes
    print("\n3. 测试 compile_notes...")
    result = await compile_notes(kb_dir="processed/编程+AI/", threshold=3)
    print(f"   ✓ 返回：{result[:100]}...")

    # 测试 publish_cards
    print("\n4. 测试 publish_cards...")
    result = await publish_cards(wiki_title="测试 Wiki")
    print(f"   ✓ 返回：{result[:100]}...")

    # 测试 get_pipeline_status
    print("\n5. 测试 get_pipeline_status...")
    result = await get_pipeline_status()
    print(f"   ✓ 返回：{result[:200]}...")

    # 测试 get_progress_text
    print("\n6. 测试 get_progress_text...")
    result = await get_progress_text()
    print(f"   ✓ 返回:\n{result}")

    # 测试 Resources
    print("\n7. 测试 ingest_status_resource...")
    result = await ingest_status_resource()
    print(f"   ✓ 返回：{result[:100]}...")

    print("\n8. 测试 digest_status_resource...")
    result = await digest_status_resource()
    print(f"   ✓ 返回：{result[:100]}...")

    print("\n9. 测试 compile_status_resource...")
    result = await compile_status_resource()
    print(f"   ✓ 返回：{result[:100]}...")

    print("\n10. 测试 publish_status_resource...")
    result = await publish_status_resource()
    print(f"   ✓ 返回：{result[:100]}...")

    print("\n11. 测试 current_progress_resource...")
    result = await current_progress_resource()
    print(f"   ✓ 返回:\n{result}")

    # 测试 Prompts
    print("\n12. 测试 daily_report prompt...")
    result = await daily_report()
    print(f"   ✓ 返回：{result[:200]}...")

    print("\n" + "=" * 60)
    print("✅ 所有 MCP Tools 测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tools())
