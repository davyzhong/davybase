import asyncio
import os
from pathlib import Path
from typing import Optional
import logging
from .config import Config
from .llm_providers.base import LLMProvider
from .llm_providers.zhipu import ZhipuProvider
from .llm_providers.minimax import MiniMaxProvider
from .writer import Writer

logger = logging.getLogger("davybase.compiler")

# 提供商配置
PROVIDERS = {
    "zhipu": {"class": ZhipuProvider, "name": "智谱 GLM5"},
    "minimax": {"class": MiniMaxProvider, "name": "MiniMax M2.7"},
}

MAX_RETRIES_PER_PROVIDER = 2  # 每个提供商最大重试次数


class Compiler:
    """LLM 编译器"""

    def __init__(self, config: Config, provider: LLMProvider, data_dir: str, vault_path: str, use_cli: bool = True):
        self.config = config
        self.provider = provider
        self.data_dir = Path(data_dir)
        self.vault_path = Path(vault_path)
        self.wiki_dir = self.vault_path / "wiki"
        self.writer = Writer(vault_path, use_cli=use_cli)

    async def run(self, provider_name: str = "zhipu"):
        """执行编译"""
        logger.info(f"开始编译（使用 {PROVIDERS.get(provider_name, {}).get('name', provider_name)}）")
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

        # 直接从 data_dir 读取原始 Markdown 文件
        for kb_dir in self.data_dir.iterdir():
            if kb_dir.is_dir() and kb_dir.name not in ("_inbox", "_failed"):
                await self._compile_knowledge_base(kb_dir, provider_name)

        logger.info("编译完成")

    async def _compile_with_fallback(self, notes: list[str], initial_provider_name: str) -> str:
        """带自动切换的编译方法 - 每个提供商重试 2 次后切换"""
        last_error = None
        attempted_providers = []

        # 从配置获取 API 密钥
        zhipu_api_key = self.config.get_llm_api_key("zhipu")
        minimax_api_key = self.config.get_llm_api_key("minimax")

        for provider_attempt in range(2):  # 最多尝试 2 个不同的提供商
            # 确定当前使用的提供商
            if provider_attempt == 0:
                current_provider_name = initial_provider_name
            else:
                # 切换到另一个提供商
                current_provider_name = "minimax" if initial_provider_name == "zhipu" else "zhipu"

            if current_provider_name in attempted_providers:
                continue

            attempted_providers.append(current_provider_name)
            provider_class = PROVIDERS[current_provider_name]["class"]
            provider_display = PROVIDERS[current_provider_name]["name"]

            # 根据提供商名称获取对应的 API 密钥
            api_key = minimax_api_key if current_provider_name == "minimax" else zhipu_api_key
            provider = provider_class(api_key)

            logger.info(f"  使用 {provider_display} (尝试 {provider_attempt+1}/2 个提供商)")

            for retry in range(MAX_RETRIES_PER_PROVIDER):
                try:
                    result = await provider.compile_notes(notes, [])
                    if provider_attempt > 0:
                        logger.info(f"  切换提供商成功：{provider_display}")
                    return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"  {provider_display} 失败 ({retry+1}/{MAX_RETRIES_PER_PROVIDER}): {e}")

                    if retry < MAX_RETRIES_PER_PROVIDER - 1:
                        # 指数退避重试
                        retry_after = min(60, 30 * (2 ** retry))
                        logger.info(f"  等待 {retry_after} 秒后重试...")
                        await asyncio.sleep(retry_after)
                    else:
                        logger.warning(f"  {provider_display} 达到最大重试次数，准备切换提供商")
                        break

        # 所有提供商都失败
        raise RuntimeError(f"所有 LLM 提供商均失败。最后错误：{last_error}")

    async def _compile_knowledge_base(self, kb_dir: Path, provider_name: str):
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
                result = await self._compile_with_fallback(batch, provider_name)
                batch_results.append(result)

            merged = await self._merge_batches(batch_results, provider_name)
            self._save_wiki_entries(merged)
        else:
            result = await self._compile_with_fallback(notes, provider_name)
            self._save_wiki_entries(result)

    async def _merge_batches(self, batch_results: list[str], provider_name: str) -> str:
        """合并多个批次的编译结果"""
        prompt = f"""以下是从同一知识库不同批次编译的 wiki 条目。合并描述相同概念的条目。保留更丰富的摘要。合并关键要点，去除重复。更新双链指向合并后的条目标题。

批次结果：
{"---BATCH---".join(batch_results)}
"""
        return await self._compile_with_fallback([prompt], provider_name)

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
