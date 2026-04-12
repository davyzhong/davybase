# main.py
import asyncio
import logging

import click

from src.config import Config
from src.compiler import Compiler
from src.converter import Converter
from src.extractor import Extractor
from src.llm_providers.minimax import MiniMaxProvider
from src.llm_providers.zhipu import ZhipuProvider
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

    api_key, client_id = config.get_getnote_credentials()
    extractor = Extractor(api_key, client_id, config.data_path)
    asyncio.run(extractor.run())


@cli.command()
@click.option("--provider", default=None, help="LLM 提供商（zhipu/minimax）")
@click.option("--no-cli", is_flag=True, help="不使用 Obsidian CLI，直接写入文件系统")
def compile_only(provider: str, no_cli: bool):
    """重新编译已有的 raw/"""
    config = Config()
    logger = setup_logging(f"{config.logs_path}/sync.log")

    provider = provider or config.default_provider
    api_key = config.get_llm_api_key(provider)

    if provider == "zhipu":
        llm_provider = ZhipuProvider(api_key)
    else:
        llm_provider = MiniMaxProvider(api_key)

    compiler = Compiler(llm_provider, config.data_path, config.vault_path, use_cli=not no_cli)
    asyncio.run(compiler.run(provider))


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

        api_key, client_id = config.get_getnote_credentials()
        provider = provider or config.default_provider
        llm_api_key = config.get_llm_api_key(provider)

        state = SyncState(f"{config.data_path}/sync.db")
        run_id = state.record_sync_run(run_type, provider)

        try:
            extractor = Extractor(api_key, client_id, config.data_path)
            await extractor.run()

            converter = Converter(config.data_path)

            if provider == "zhipu":
                llm_provider = ZhipuProvider(llm_api_key)
            else:
                llm_provider = MiniMaxProvider(llm_api_key)

            compiler = Compiler(llm_provider, config.data_path, config.vault_path, use_cli=use_cli)
            await compiler.run(provider)

            state.complete_sync_run(run_id, 0, 0, 0)
            logger.info("同步完成")

        except Exception as e:
            logger.exception(f"同步失败：{e}")
            state.complete_sync_run(run_id, 0, 0, 1)


if __name__ == "__main__":
    cli()
