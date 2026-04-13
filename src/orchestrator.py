#!/usr/bin/env python3
"""
Davybase 并发管线编排器

提供统一的并发执行调度能力：
- IngestOrchestrator: 并发抽取笔记
- DigestOrchestrator: 并发消化笔记（生成标题、分类、移动）
- CompileOrchestrator: 并发编译 Wiki 条目

Usage:
    from src.orchestrator import IngestOrchestrator

    orchestrator = IngestOrchestrator(state_dir, config)
    result = await orchestrator.run(batch_size=20, concurrency=3, resume=True)
"""
import asyncio
import hashlib
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from src.config import Config
from src.processing_status import (
    IngestStatus, DigestStatus, CompileStatus,
    IngestRecord, DigestRecord, CompileRecord
)
from src.extractor import Extractor, GetNoteClient
from src.llm_providers.base import LLMProvider
from src.llm_providers.zhipu import ZhipuProvider
from src.llm_providers.minimax import MiniMaxProvider
from src.llm_providers.qwen import QwenProvider
from src.writer import Writer

logger = logging.getLogger("davybase.orchestrator")


# =============================================================================
# 工具函数
# =============================================================================

def compute_content_hash(content: str) -> str:
    """计算内容哈希"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


# =============================================================================
# Ingest Orchestrator - 并发抽取
# =============================================================================

class IngestOrchestrator:
    """并发抽取编排器"""

    def __init__(self, state_dir: Path, config: Config):
        self.state_dir = state_dir
        self.config = config
        self.state = IngestStatus(state_dir)
        self.raw_dir = Path(config.raw_path) if hasattr(config, 'raw_path') else Path(config.vault_path) / "raw"
        self.api_key, self.client_id = config.get_getnote_credentials()

    async def run(
        self,
        batch_size: int = 20,
        concurrency: int = 3,
        resume: bool = True,
        source: str = "getnote"
    ) -> Dict[str, Any]:
        """
        执行并发抽取

        Args:
            batch_size: 单批次最大抽取数量
            concurrency: 并发请求数
            resume: 是否从中断处恢复
            source: 数据来源 getnote|local

        Returns:
            抽取结果字典
        """
        start_time = time.time()
        logger.info(f"开始并发抽取 (batch_size={batch_size}, concurrency={concurrency})")

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        inbox_dir = self.raw_dir / "notes" / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        if source != "getnote":
            raise NotImplementedError(f"暂不支持 {source} 源")

        # 获取已抽取 ID 列表（幂等性检查）
        extracted_ids = self.state.get_extracted_ids()
        logger.info(f"已抽取 {len(extracted_ids)} 条笔记")

        total_extracted = 0
        failed = 0

        async with GetNoteClient(self.api_key, self.client_id) as client:
            # 获取知识库笔记
            kbs = await client.list_knowledge_bases()
            logger.info(f"发现 {len(kbs)} 个知识库")

            for kb in kbs:
                kb_result = await self._extract_knowledge_base(
                    client, kb, batch_size, concurrency, extracted_ids
                )
                total_extracted += kb_result["extracted"]
                failed += kb_result["failed"]

            # 抽取散落笔记
            inbox_result = await self._extract_inbox_notes(
                client, batch_size, concurrency, extracted_ids
            )
            total_extracted += inbox_result["extracted"]
            failed += inbox_result["failed"]

        duration = time.time() - start_time
        logger.info(f"抽取完成：{total_extracted} 条，失败 {failed} 条，耗时 {duration:.1f}秒")

        return {
            "total": total_extracted,
            "failed": failed,
            "duration": round(duration, 1)
        }

    async def _extract_knowledge_base(
        self,
        client: GetNoteClient,
        kb: dict,
        batch_size: int,
        concurrency: int,
        extracted_ids: set
    ) -> Dict[str, int]:
        """抽取单个知识库"""
        kb_name = kb["name"]
        kb_dir = self.raw_dir / "notes" / kb_name
        kb_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"抽取知识库 \"{kb_name}\"")

        # 获取知识库所有笔记
        all_notes = []
        page = 1
        has_more = True
        while has_more:
            notes, has_more = await client.list_knowledge_notes(kb["topic_id"], page)
            all_notes.extend(notes)
            page += 1
            if has_more:
                await asyncio.sleep(0.5)

        # 过滤已抽取的
        pending_notes = [n for n in all_notes if n["note_id"] not in extracted_ids]
        logger.info(f"  共 {len(all_notes)} 条，待抽取 {len(pending_notes)} 条")

        if not pending_notes:
            return {"extracted": 0, "failed": 0}

        # 分批次
        batches = [pending_notes[i:i+batch_size] for i in range(0, len(pending_notes), batch_size)]
        logger.info(f"  分为 {len(batches)} 个批次")

        # 并发抽取
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(*[
            self._extract_batch(client, batch, kb_dir, kb_name, semaphore)
            for batch in batches
        ], return_exceptions=True)

        # 聚合结果
        total_extracted = sum(r.get("extracted", 0) for r in results if isinstance(r, dict))
        failed = sum(r.get("failed", 0) for r in results if isinstance(r, dict))

        return {"extracted": total_extracted, "failed": failed}

    async def _extract_inbox_notes(
        self,
        client: GetNoteClient,
        batch_size: int,
        concurrency: int,
        extracted_ids: set
    ) -> Dict[str, int]:
        """抽取散落笔记"""
        inbox_dir = self.raw_dir / "notes" / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info("抽取散落笔记")

        # 获取所有笔记
        all_notes = await client.list_all_notes()
        pending_notes = [n for n in all_notes if n["note_id"] not in extracted_ids]
        logger.info(f"  全部笔记 {len(all_notes)} 条，待抽取 {len(pending_notes)} 条")

        if not pending_notes:
            return {"extracted": 0, "failed": 0}

        # 分批次
        batches = [pending_notes[i:i+batch_size] for i in range(0, len(pending_notes), batch_size)]

        # 并发抽取
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(*[
            self._extract_batch(client, batch, inbox_dir, "_inbox", semaphore)
            for batch in batches
        ], return_exceptions=True)

        total_extracted = sum(r.get("extracted", 0) for r in results if isinstance(r, dict))
        failed = sum(r.get("failed", 0) for r in results if isinstance(r, dict))

        return {"extracted": total_extracted, "failed": failed}

    async def _extract_batch(
        self,
        client: GetNoteClient,
        notes_batch: list,
        kb_dir: Path,
        kb_name: str,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, int]:
        """并发抽取一批笔记"""
        async with semaphore:
            tasks = [self._extract_single_note(client, note, kb_dir, kb_name) for note in notes_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            extracted = sum(1 for r in results if r is True)
            failed = len(results) - extracted

            return {"extracted": extracted, "failed": failed}

    async def _extract_single_note(
        self,
        client: GetNoteClient,
        note: dict,
        kb_dir: Path,
        kb_name: str
    ) -> bool:
        """抽取单条笔记"""
        note_id = note["note_id"]

        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.3)  # 请求间隔

            # 格式化内容
            content = self._format_note_content(detail)
            filename = self._sanitize_filename(detail.get('title', '无标题'))

            # 保存文件
            note_file = kb_dir / f"{filename}.md"
            note_file.write_text(content, encoding="utf-8")

            # 更新状态
            record = IngestRecord(
                note_id=note_id,
                source="getnote",
                raw_path=str(note_file),
                ingested_at=datetime.now().isoformat(),
                content_hash=compute_content_hash(content)
            )
            self.state.mark_processed(note_id, record)

            logger.debug(f"  ✓ 抽取 {note_id}: {detail.get('title', '无标题')}")
            return True

        except Exception as e:
            logger.error(f"  ✗ 抽取 {note_id} 失败：{e}")
            return False

    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()[:80]

    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        title = detail.get('title', '')
        if not title:
            content = detail.get("content", "")
            first_line = content.split('\n')[0].strip()[:50]
            if first_line and first_line != '#':
                title = first_line
            else:
                title = detail.get('note_id', '无标题')

        lines = [
            "---",
            f"note_id: {detail.get('note_id', '')}",
            f"note_type: {detail.get('note_type', '')}",
            f"created_at: {detail.get('created_at', '')}",
            f"title: {title}",
            f"tags: {detail.get('tags', [])}",
            "---",
            "",
            f"# {title}",
            "",
            detail.get("content", ""),
        ]

        if detail.get("web_page", {}).get("content"):
            lines.extend([
                "",
                "---",
                "## 原文链接",
                "",
                detail["web_page"]["content"],
            ])

        return "\n".join(lines)


# =============================================================================
# Digest Orchestrator - 并发消化
# =============================================================================

class DigestOrchestrator:
    """并发消化编排器"""

    def __init__(self, state_dir: Path, config: Config):
        self.state_dir = state_dir
        self.config = config
        self.state = DigestStatus(state_dir)
        self.raw_dir = Path(config.raw_path) if hasattr(config, 'raw_path') else Path(config.vault_path) / "raw"
        self.processed_dir = Path(config.data_path) if hasattr(config, 'data_path') else Path(config.vault_path) / "processed"

        # 初始化 LLM 提供商
        self.providers = {
            "qwen": QwenProvider(config.get_llm_api_key("qwen")),
            "zhipu": ZhipuProvider(config.get_llm_api_key("zhipu")),
            "minimax": MiniMaxProvider(config.get_llm_api_key("minimax"))
        }

    def _select_provider(self, index: int, strategy: str) -> LLMProvider:
        """根据策略选择 LLM 提供商"""
        keys = list(self.providers.keys())
        if strategy == "round_robin":
            return self.providers[keys[index % len(keys)]]
        elif strategy == "weighted":
            # 60% 千问，25% 智谱，15% MiniMax
            import random
            r = random.random()
            if r < 0.6:
                return self.providers["qwen"]
            elif r < 0.85:
                return self.providers["zhipu"]
            else:
                return self.providers["minimax"]
        else:  # single
            return self.providers["qwen"]

    async def run(
        self,
        inbox_dir: str = "raw/notes/_inbox/",
        apply: bool = False,
        limit: Optional[int] = None,
        provider: str = "minimax",
        provider_rotation: str = "round_robin",
        concurrency: int = 5
    ) -> Dict[str, Any]:
        """
        执行并发消化

        Args:
            inbox_dir: 待处理笔记目录 (相对于 vault_path 或绝对路径)
            apply: 是否直接执行移动
            limit: 限制处理数量
            provider: 首选 LLM 提供商
            provider_rotation: LLM 分配策略
            concurrency: 并发任务数

        Returns:
            消化结果字典
        """
        start_time = time.time()
        logger.info(f"开始并发消化 (concurrency={concurrency}, provider_rotation={provider_rotation})")

        # 处理路径（支持相对路径和绝对路径）
        if inbox_dir.startswith('/'):
            notes_path = Path(inbox_dir)
        else:
            # 相对于 vault_path 的路径
            notes_path = Path(self.config.vault_path) / inbox_dir

        if not notes_path.exists():
            logger.warning(f"目录不存在：{notes_path}")
            return {
                "total_processed": 0,
                "total_classified": 0,
                "total_moved": 0,
                "failed": 0,
                "duration": 0
            }

        # 获取待处理笔记文件
        note_files = list(notes_path.glob("*.md"))
        logger.info(f"扫描到 {len(note_files)} 条笔记")

        # 过滤已处理的（幂等性检查）
        pending_files = []
        for f in note_files:
            note_id = self._extract_note_id(f)
            if note_id and not self.state.is_processed(note_id):
                pending_files.append(f)

        logger.info(f"待处理：{len(pending_files)} 条（已跳过 {len(note_files) - len(pending_files)} 条）")

        if not pending_files:
            return {
                "total_processed": 0,
                "total_classified": 0,
                "total_moved": 0,
                "failed": 0,
                "duration": 0
            }

        # 限制数量
        if limit:
            pending_files = pending_files[:limit]

        # 分批次
        batch_size = 10
        batches = [pending_files[i:i+batch_size] for i in range(0, len(pending_files), batch_size)]

        # 并发处理
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(*[
            self._process_batch(batch, i, provider, provider_rotation, apply, semaphore)
            for i, batch in enumerate(batches)
        ], return_exceptions=True)

        # 聚合结果
        total_processed = sum(r.get("processed", 0) for r in results if isinstance(r, dict))
        total_classified = sum(r.get("classified", 0) for r in results if isinstance(r, dict))
        total_moved = sum(r.get("moved", 0) for r in results if isinstance(r, dict))
        failed = sum(r.get("failed", 0) for r in results if isinstance(r, dict))

        duration = time.time() - start_time
        logger.info(f"消化完成：处理 {total_processed} 条，移动 {total_moved} 条，失败 {failed} 条，耗时 {duration:.1f}秒")

        return {
            "total_processed": total_processed,
            "total_classified": total_classified,
            "total_moved": total_moved,
            "failed": failed,
            "duration": round(duration, 1)
        }

    def _extract_note_id(self, file_path: Path) -> Optional[str]:
        """从笔记文件中提取 note_id"""
        try:
            content = file_path.read_text(encoding='utf-8')
            for line in content.split('\n')[:10]:  # 只检查 frontmatter 区域
                if line.startswith('note_id:'):
                    return line.split(':', 1)[1].strip()
        except Exception:
            pass
        return None

    async def _process_batch(
        self,
        files: List[Path],
        batch_index: int,
        preferred_provider: str,
        provider_rotation: str,
        apply: bool,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, int]:
        """处理一批笔记"""
        async with semaphore:
            # 选择 LLM 提供商
            provider = self._select_provider(batch_index, provider_rotation)
            provider_name = "智谱" if provider == self.providers.get("zhipu") else "MiniMax"
            logger.info(f"批次 {batch_index}: 使用 {provider_name}, {len(files)} 条笔记")

            results = []
            for f in files:
                result = await self._digest_single_file(f, provider, apply)
                results.append(result)

            processed = sum(1 for r in results if r["success"])
            classified = sum(1 for r in results if r.get("classified", False))
            moved = sum(1 for r in results if r.get("moved", False))
            failed = len(results) - processed

            return {
                "processed": processed,
                "classified": classified,
                "moved": moved,
                "failed": failed
            }

    async def _digest_single_file(
        self,
        file_path: Path,
        provider: LLMProvider,
        apply: bool
    ) -> Dict[str, Any]:
        """消化单个笔记文件"""
        note_id = self._extract_note_id(file_path)
        if not note_id:
            return {"success": False, "error": "无法提取 note_id"}

        try:
            # 读取笔记内容
            content = file_path.read_text(encoding='utf-8')

            # 调用 LLM 生成标题和分类
            result = await provider.digest_note(content)
            title = result["title"]
            recommended_kb = result["category"]
            confidence = result["confidence"]
            tags = result["tags"]

            logger.debug(f"  ✓ 消化 {note_id}: 标题='{title}', 分类='{recommended_kb}', 置信度={confidence}")

            # 更新状态
            self.state.mark_summarized(note_id, title)
            self.state.mark_classified(note_id, recommended_kb, "use_llm", confidence)

            if apply:
                # 移动到知识库
                kb_dir = self.processed_dir / recommended_kb
                kb_dir.mkdir(parents=True, exist_ok=True)
                dest_path = kb_dir / file_path.name

                # 复制文件
                import shutil
                shutil.copy2(file_path, dest_path)

                self.state.mark_moved(note_id, recommended_kb)

                return {
                    "success": True,
                    "classified": True,
                    "moved": True,
                    "title": title,
                    "kb": recommended_kb,
                    "confidence": confidence,
                    "tags": tags
                }
            else:
                return {
                    "success": True,
                    "classified": True,
                    "moved": False,
                    "title": title,
                    "kb": recommended_kb,
                    "confidence": confidence,
                    "tags": tags
                }

        except Exception as e:
            logger.error(f"  ✗ 消化 {note_id} 失败：{e}")
            return {"success": False, "error": str(e)}


# =============================================================================
# Compile Orchestrator - 并发编译
# =============================================================================

class CompileOrchestrator:
    """并发编译编排器"""

    def __init__(self, state_dir: Path, config: Config):
        self.state_dir = state_dir
        self.config = config
        self.state = CompileStatus(state_dir)
        self.processed_dir = Path(config.data_path) if hasattr(config, 'data_path') else Path(config.vault_path) / "processed"
        self.vault_path = Path(config.vault_path)
        self.writer = Writer(str(config.vault_path), use_cli=True)

        # 初始化 LLM 提供商
        self.providers = {
            "qwen": QwenProvider(config.get_llm_api_key("qwen")),
            "zhipu": ZhipuProvider(config.get_llm_api_key("zhipu")),
            "minimax": MiniMaxProvider(config.get_llm_api_key("minimax"))
        }

    def _select_provider(self, index: int, strategy: str) -> LLMProvider:
        """根据策略选择 LLM 提供商"""
        keys = list(self.providers.keys())
        if strategy == "round_robin":
            return self.providers[keys[index % len(keys)]]
        elif strategy == "weighted":
            # 60% MiniMax, 40% 千问
            import random
            r = random.random()
            if r < 0.6:
                return self.providers["minimax"]
            else:
                return self.providers["qwen"]
        else:  # single
            return self.providers["minimax"]

    async def run(
        self,
        kb_dir: str,
        threshold: int = 3,
        provider: str = "zhipu",
        provider_rotation: str = "round_robin",
        concurrent_batches: int = 2
    ) -> Dict[str, Any]:
        """
        执行并发编译

        Args:
            kb_dir: 知识库目录
            threshold: 触发编译的最小笔记数
            provider: 首选 LLM 提供商
            provider_rotation: LLM 分配策略
            concurrent_batches: 同时编译的批次数量

        Returns:
            编译结果字典
        """
        start_time = time.time()
        logger.info(f"开始并发编译 (concurrent_batches={concurrent_batches}, provider_rotation={provider_rotation})")

        # 读取知识库笔记
        kb_path = self.vault_path / kb_dir
        if not kb_path.exists():
            logger.warning(f"目录不存在：{kb_path}")
            return {
                "total_wiki_entries": 0,
                "failed": 0,
                "duration": 0
            }

        # 获取所有笔记文件
        note_files = list(kb_path.glob("*.md"))
        logger.info(f"扫描到 {len(note_files)} 条笔记")

        if len(note_files) < threshold:
            logger.info(f"笔记数量 ({len(note_files)}) 少于阈值 ({threshold})，跳过编译")
            return {
                "total_wiki_entries": 0,
                "failed": 0,
                "duration": 0
            }

        # 分批次
        batch_size = 15
        batches = [note_files[i:i+batch_size] for i in range(0, len(note_files), batch_size)]
        logger.info(f"分为 {len(batches)} 个批次")

        # 并发编译
        semaphore = asyncio.Semaphore(concurrent_batches)
        results = await asyncio.gather(*[
            self._compile_batch(batch, i, provider, provider_rotation, semaphore)
            for i, batch in enumerate(batches)
        ], return_exceptions=True)

        # 聚合结果
        total_wiki_entries = sum(r.get("wiki_entries", 0) for r in results if isinstance(r, dict))
        failed = sum(r.get("failed", 0) for r in results if isinstance(r, dict))

        duration = time.time() - start_time
        logger.info(f"编译完成：生成 {total_wiki_entries} 个 Wiki 条目，失败 {failed} 条，耗时 {duration:.1f}秒")

        return {
            "total_wiki_entries": total_wiki_entries,
            "failed": failed,
            "duration": round(duration, 1)
        }

    async def _compile_batch(
        self,
        files: List[Path],
        batch_index: int,
        preferred_provider: str,
        provider_rotation: str,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, int]:
        """编译一批笔记"""
        async with semaphore:
            # 选择 LLM 提供商
            provider = self._select_provider(batch_index, provider_rotation)
            provider_name = "智谱" if provider == self.providers.get("zhipu") else "MiniMax"
            logger.info(f"编译批次 {batch_index}: 使用 {provider_name}, {len(files)} 条笔记")

            try:
                # 读取笔记内容
                notes_content = [f.read_text(encoding='utf-8') for f in files]

                # 调用 LLM 编译
                # TODO: 实现实际的 LLM 编译逻辑
                # 这里暂时返回一个占位结果
                wiki_entries = 1  # 假设生成 1 个 Wiki 条目

                return {
                    "wiki_entries": wiki_entries,
                    "failed": 0
                }

            except Exception as e:
                logger.error(f"编译批次 {batch_index} 失败：{e}")
                return {
                    "wiki_entries": 0,
                    "failed": len(files)
                }


# =============================================================================
# 主函数 - CLI 入口
# =============================================================================

if __name__ == "__main__":
    import click

    @click.group()
    def cli():
        """Davybase 并发管线编排器"""
        pass

    @cli.command()
    @click.option("--batch-size", default=20)
    @click.option("--concurrency", default=3)
    @click.option("--resume", is_flag=True, default=True)
    def ingest(batch_size: int, concurrency: int, resume: bool):
        """并发抽取笔记"""
        config = Config()
        state_dir = Path(config.vault_path) / ".davybase" / "progress"
        orchestrator = IngestOrchestrator(state_dir, config)
        result = asyncio.run(orchestrator.run(
            batch_size=batch_size,
            concurrency=concurrency,
            resume=resume
        ))
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    @cli.command()
    @click.option("--concurrency", default=5)
    @click.option("--provider-rotation", default="round_robin")
    @click.option("--apply", is_flag=True)
    def digest(concurrency: int, provider_rotation: str, apply: bool):
        """并发消化笔记"""
        config = Config()
        state_dir = Path(config.vault_path) / ".davybase" / "progress"
        orchestrator = DigestOrchestrator(state_dir, config)
        result = asyncio.run(orchestrator.run(
            concurrency=concurrency,
            provider_rotation=provider_rotation,
            apply=apply
        ))
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    @cli.command()
    @click.option("--kb-dir", required=True)
    @click.option("--concurrent-batches", default=2)
    @click.option("--provider-rotation", default="round_robin")
    def compile(kb_dir: str, concurrent_batches: int, provider_rotation: str):
        """并发编译 Wiki"""
        config = Config()
        state_dir = Path(config.vault_path) / ".davybase" / "progress"
        orchestrator = CompileOrchestrator(state_dir, config)
        result = asyncio.run(orchestrator.run(
            kb_dir=kb_dir,
            concurrent_batches=concurrent_batches,
            provider_rotation=provider_rotation
        ))
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    cli()
