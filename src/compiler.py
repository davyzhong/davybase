import asyncio
from pathlib import Path
from typing import Optional
import logging
from .llm_providers.base import LLMProvider
from .llm_providers.zhipu import ZhipuProvider
from .llm_providers.minimax import MiniMaxProvider
from .writer import Writer

logger = logging.getLogger("davybase.compiler")


class Compiler:
    """LLM 编译器"""

    def __init__(self, provider: LLMProvider, data_dir: str, vault_path: str, use_cli: bool = True):
        self.provider = provider
        self.data_dir = Path(data_dir)
        self.vault_path = Path(vault_path)
        self.wiki_dir = self.vault_path / "wiki"
        self.writer = Writer(vault_path, use_cli=use_cli)

    async def run(self, provider_name: str = "zhipu"):
        """执行编译"""
        logger.info(f"开始编译（使用 {provider_name}）")
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

        raw_dir = self.data_dir / "raw"
        for kb_dir in raw_dir.iterdir():
            if kb_dir.is_dir() and kb_dir.name != "_inbox":
                await self._compile_knowledge_base(kb_dir)

        logger.info("编译完成")

    async def _compile_knowledge_base(self, kb_dir: Path):
        """编译单个知识库"""
        kb_name = kb_dir.name
        logger.info(f"编译知识库 \"{kb_name}\"")

        notes = []
        for note_file in kb_dir.glob("*.md"):
            if note_file.stem != "_inbox":
                notes.append(note_file.read_text(encoding="utf-8"))

        if not notes:
            logger.warning(f"  知识库 \"{kb_name}\" 无笔记，跳过")
            return

        batch_size = 15
        if len(notes) > batch_size:
            batches = [notes[i : i + batch_size] for i in range(0, len(notes), batch_size)]
            batch_results = []
            for i, batch in enumerate(batches):
                logger.info(f"  编译批次 {i+1}/{len(batches)}")
                result = await self.provider.compile_notes(batch, [])
                batch_results.append(result)

            merged = await self._merge_batches(batch_results)
            self._save_wiki_entries(merged)
        else:
            result = await self.provider.compile_notes(notes, [])
            self._save_wiki_entries(result)

    async def _merge_batches(self, batch_results: list[str]) -> str:
        """合并多个批次的编译结果"""
        prompt = f"""以下是从同一知识库不同批次编译的 wiki 条目。合并描述相同概念的条目。保留更丰富的摘要。合并关键要点，去除重复。更新双链指向合并后的条目标题。

批次结果：
{"---BATCH---".join(batch_results)}
"""
        return await self.provider.chat([{"role": "user", "content": prompt}])

    def _save_wiki_entries(self, content: str):
        """保存 wiki 条目"""
        entries = content.split("---ENTRY---")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            self.writer.write(entry)

    def _extract_title(self, content: str) -> Optional[str]:
        """从内容中提取标题"""
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return None

    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()
