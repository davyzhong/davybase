# main.py
import asyncio
import logging
from pathlib import Path

import click

from src.config import Config
from src.compiler import Compiler
from src.converter import Converter
from src.extractor import Extractor
from src.llm_providers.minimax import MiniMaxProvider
from src.llm_providers.zhipu import ZhipuProvider
from src.llm_providers.qwen import QwenProvider
from src.orchestrator import IngestOrchestrator, DigestOrchestrator, CompileOrchestrator
from src.sync_state import SyncState
from src.utils import LockFile, setup_logging


@click.group()
def cli():
    """Davybase - get 笔记到 Obsidian Wiki 的知识库管线"""
    pass


@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
@click.option("--no-cli", is_flag=True, help="不使用 Obsidian CLI，直接写入文件系统")
def full_sync(provider: str, no_cli: bool):
    """全量同步"""
    asyncio.run(run_sync("full", provider, use_cli=not no_cli))


@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
@click.option("--no-cli", is_flag=True, help="不使用 Obsidian CLI，直接写入文件系统")
def incremental(provider: str, no_cli: bool):
    """增量同步"""
    asyncio.run(run_sync("incremental", provider, use_cli=not no_cli))


@cli.command()
def extract_only():
    """仅抽取，不编译"""
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")

    extractor = Extractor(config, config.data_path)
    asyncio.run(extractor.run())


@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax/qwen）")
@click.option("--no-cli", is_flag=True, help="不使用 Obsidian CLI，直接写入文件系统")
def compile_only(provider: str, no_cli: bool):
    """重新编译已有的 raw/"""
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")

    provider = provider or config.default_provider

    if provider == "zhipu":
        llm_provider = ZhipuProvider(config.get_llm_api_key("zhipu"))
    elif provider == "minimax":
        llm_provider = MiniMaxProvider(config.get_llm_api_key("minimax"))
    elif provider == "qwen":
        llm_provider = QwenProvider(config.get_llm_api_key("qwen"))
    else:
        raise ValueError(f"不支持的 LLM 提供商：{provider}")

    compiler = Compiler(config, llm_provider, config.data_path, config.vault_path, use_cli=not no_cli)
    asyncio.run(compiler.run(provider))


# =============================================================================
# 并发管线命令 (v4.0)
# =============================================================================

@cli.command()
@click.option("--batch-size", default=None, type=int, help="单批次最大抽取数量（默认从配置文件读取）")
@click.option("--concurrency", default=None, type=int, help="并发请求数（默认从配置文件读取）")
@click.option("--resume", is_flag=True, default=None, help="断点续传（默认从配置文件读取）")
@click.option("--source", default="getnote", help="数据来源")
def ingest(batch_size: int, concurrency: int, resume: bool, source: str):
    """并发抽取笔记（v4.0）"""
    config = Config()
    state_dir = Path(config.vault_path) / ".davybase" / "progress"
    orchestrator = IngestOrchestrator(state_dir, config)
    result = asyncio.run(orchestrator.run(
        batch_size=batch_size,
        concurrency=concurrency,
        resume=resume,
        source=source
    ))
    click.echo(f"抽取完成：{result['total']} 条，失败 {result['failed']} 条，耗时 {result['duration']}秒")


@cli.command()
@click.option("--inbox-dir", default=None, help="待处理笔记目录")
@click.option("--worker-mode", default=None, help="Worker 模式：pool|batch（默认从配置文件读取）")
@click.option("--workers", default=None, help="Worker 配置 JSON 字符串（默认从配置文件读取）")
@click.option("--concurrency", default=None, type=int, help="并发任务数（默认从配置文件读取）")
@click.option("--provider-rotation", default=None, help="LLM 分配策略（默认从配置文件读取）")
@click.option("--apply", is_flag=True, default=None, help="直接执行移动（默认从配置文件读取）")
@click.option("--limit", type=int, default=None, help="限制处理数量")
def digest(inbox_dir: str, worker_mode: str, workers: str, concurrency: int, provider_rotation: str, apply: bool, limit: int):
    """并发消化笔记（v4.0）"""
    import json

    config = Config()
    state_dir = Path(config.vault_path) / ".davybase" / "progress"
    orchestrator = DigestOrchestrator(state_dir, config)

    # CLI 覆盖配置
    if worker_mode:
        orchestrator.worker_mode = worker_mode
    if workers:
        orchestrator.worker_configs = json.loads(workers)

    result = asyncio.run(orchestrator.run(
        inbox_dir=inbox_dir,
        apply=apply,
        limit=limit,
        provider_rotation=provider_rotation,
        concurrency=concurrency
    ))

    # 显示详细结果
    click.echo(f"消化完成：处理 {result['total_processed']} 条，移动 {result['total_moved']} 条，失败 {result['failed']} 条")
    if 'by_provider' in result:
        for provider, stats in result['by_provider'].items():
            click.echo(f"  {provider}: ✓{stats['success']} ✗{stats['failed']}")


@cli.command()
@click.option("--kb-dir", required=True, help="知识库目录")
@click.option("--threshold", default=None, type=int, help="触发编译的最小笔记数（默认从配置文件读取）")
@click.option("--concurrent-batches", default=None, type=int, help="同时编译的批次数量（默认从配置文件读取）")
@click.option("--provider-rotation", default=None, help="LLM 分配策略（默认从配置文件读取）")
def compile(kb_dir: str, threshold: int, concurrent_batches: int, provider_rotation: str):
    """并发编译 Wiki（v4.0）"""
    config = Config()
    state_dir = Path(config.vault_path) / ".davybase" / "progress"
    orchestrator = CompileOrchestrator(state_dir, config)
    result = asyncio.run(orchestrator.run(
        kb_dir=kb_dir,
        threshold=threshold,
        concurrent_batches=concurrent_batches,
        provider_rotation=provider_rotation
    ))
    click.echo(f"编译完成：生成 {result['total_wiki_entries']} 个 Wiki 条目，失败 {result['failed']} 条")


@cli.command()
@click.option("--full", is_flag=True, help="执行全量管道")
@click.option("--resume", is_flag=True, default=None, help="断点续传")
@click.option("--ingest-batch-size", default=None, type=int, help="摄取批次大小")
@click.option("--ingest-concurrency", default=None, type=int, help="摄取并发数")
@click.option("--digest-concurrency", default=None, type=int, help="消化并发数")
@click.option("--compile-batch-size", default=None, type=int, help="编译批次大小")
@click.option("--compile-concurrent-batches", default=None, type=int, help="编译并发批次数")
def pipeline(full: bool, resume: bool, ingest_batch_size: int, ingest_concurrency: int,
             digest_concurrency: int, compile_batch_size: int, compile_concurrent_batches: int):
    """全量管道（一键执行所有阶段）"""
    config = Config()
    state_dir = Path(config.vault_path) / ".davybase" / "progress"

    async def run_pipeline():
        # 阶段 1: 摄取
        click.echo("=== 阶段 1: 摄取 ===")
        ingest_orch = IngestOrchestrator(state_dir, config)
        ingest_result = await ingest_orch.run(
            batch_size=ingest_batch_size,
            concurrency=ingest_concurrency,
            resume=resume
        )
        click.echo(f"摄取：{ingest_result['total']} 条")

        # 阶段 2: 消化
        click.echo("=== 阶段 2: 消化 ===")
        digest_orch = DigestOrchestrator(state_dir, config)
        digest_result = await digest_orch.run(
            apply=True,
            concurrency=digest_concurrency
        )
        click.echo(f"消化：移动 {digest_result['total_moved']} 条")

        # 阶段 3: 编译
        click.echo("=== 阶段 3: 编译 ===")
        compile_orch = CompileOrchestrator(state_dir, config)
        compile_result = await compile_orch.run(
            kb_dir="processed/",
            batch_size=compile_batch_size,
            concurrent_batches=compile_concurrent_batches
        )
        click.echo(f"编译：{compile_result['total_wiki_entries']} 个 Wiki 条目")

    asyncio.run(run_pipeline())


@cli.command()
def status():
    """查看同步状态"""
    config = Config()
    state = SyncState(f"{config.data_path}/sync.db")
    s = state.get_status()

    click.echo(
        f"上次同步：{s['last_run']['completed_at'] if s['last_run'] else '无'} "
        f"({s['last_run']['run_type'] if s['last_run'] else ''}, "
        f"{s['last_run']['provider'] if s['last_run'] else ''})"
    )
    click.echo(f"已同步笔记：{s['total_notes']}")
    click.echo(f"Wiki 条目：{s['wiki_entries']}")
    click.echo(f"失败：{s['failed_count']}")


@cli.command()
def quota():
    """检查 get 笔记 API 配额"""
    import subprocess

    result = subprocess.run(
        ["getnote", "quota", "-o", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(result.stdout)
    else:
        click.echo(f"查询失败：{result.stderr}")


async def run_sync(run_type: str, provider: str, use_cli: bool = True):
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")

    lock_path = f"{config.data_path}/.sync.lock"
    with LockFile(lock_path) as lock:
        if not lock.acquired:
            logger.error("另一个同步进程正在运行")
            return

        provider = provider or config.default_provider

        state = SyncState(f"{config.data_path}/sync.db")
        run_id = state.record_sync_run(run_type, provider)

        try:
            # 抽取
            extractor = Extractor(config, config.data_path)
            await extractor.run()

            # 转换
            converter = Converter(config.data_path)

            # 编译
            if provider == "zhipu":
                llm_provider = ZhipuProvider(config.get_llm_api_key("zhipu"))
            else:
                llm_provider = MiniMaxProvider(config.get_llm_api_key("minimax"))

            compiler = Compiler(config, llm_provider, config.data_path, config.vault_path, use_cli=use_cli)
            await compiler.run(provider)

            state.complete_sync_run(run_id, 0, 0, 0)
            logger.info("同步完成")

        except Exception as e:
            logger.exception(f"同步失败：{e}")
            state.complete_sync_run(run_id, 0, 0, 1)


if __name__ == "__main__":
    cli()
