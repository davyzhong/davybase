import asyncio
import httpx
import logging
from .base import LLMProvider

logger = logging.getLogger("davybase.llm")

COMPILE_PROMPT = """你是一个知识库编辑。以下是从 get 笔记导出的原始笔记（Markdown 格式）。
请完成以下任务：

1. 阅读所有笔记，识别其中的核心概念和主题
2. 为每个核心概念创建一个 wiki 条目，包含：
   - 核心摘要（200 字以内）
   - 关键要点（要点列表）
   - 与其他概念的关系（使用 [[双链]] 格式）
3. 每个条目必须包含 frontmatter（title, source, tags, created, type）
4. 使用 Obsidian Flavored Markdown 格式
5. 用 %%davybase-auto-begin%% 和 %%davybase-auto-end%% 标记包裹所有自动生成的内容

输出格式：每个 wiki 条目为一个文件，条目之间用 "---ENTRY---" 分隔

原始笔记：
{notes}

已有 wiki 条目（用于交叉引用）：
{existing_wiki}
"""


class MiniMaxProvider(LLMProvider):
    """MiniMax M2.7 提供商"""

    BASE_URL = "https://api.minimaxi.com/v1/chat/completions"
    MODEL = "codex-MiniMax-M2.7"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # 增加超时时间：2 分钟读取超时
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0)) as client:
                    response = await client.post(
                        self.BASE_URL,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": self.MODEL, "messages": messages, **kwargs},
                    )
                    if response.status_code == 429:
                        # 指数退避：10s, 20s, 40s, 60s, 60s
                        retry_after = min(60, 10 * (2 ** attempt))
                        logger.warning(f"MiniMax API 触发限流，等待 {retry_after} 秒（第 {attempt+1}/{max_retries} 次重试）")
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = min(60, 10 * (2 ** attempt))
                    logger.warning(f"MiniMax API 触发限流，等待 {retry_after} 秒（第 {attempt+1}/{max_retries} 次重试）")
                    await asyncio.sleep(retry_after)
                else:
                    raise
            except httpx.ReadTimeout as e:
                if attempt < max_retries - 1:
                    retry_after = min(60, 30 * (2 ** attempt))
                    logger.warning(f"MiniMax API 读取超时，等待 {retry_after} 秒后重试（第 {attempt+1}/{max_retries} 次）")
                    await asyncio.sleep(retry_after)
                else:
                    raise RuntimeError(f"MiniMax API 调用失败：超过最大重试次数（最后错误：读取超时）")
        raise RuntimeError("MiniMax API 调用失败：超过最大重试次数")

    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        prompt = COMPILE_PROMPT.format(
            notes="\n\n".join(notes),
            existing_wiki="\n\n".join(existing_wiki) if existing_wiki else "无",
        )
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature=0.7)
