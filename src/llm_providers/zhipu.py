import asyncio
import httpx
import logging
import json
from typing import Dict
from .base import LLMProvider, DigestResult

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

DIGEST_PROMPT = """你是一个知识库助手。请阅读以下笔记内容，然后以 JSON 格式返回：
1. title: 一个简洁、准确的标题（10-20 字）
2. category: 推荐的知识库分类（从以下选择：编程、AI+ 机器学习、产品管理、设计模式、系统架构、数据库、前端开发、后端开发、DevOps、未分类）
3. confidence: 分类置信度（"high"、"medium"、"low"）
4. tags: 3-5 个关键词标签

笔记内容：
{content}

请只返回 JSON，不要任何其他内容。格式如下：
{{"title": "标题", "category": "分类", "confidence": "high", "tags": ["tag1", "tag2"]}}
"""


class ZhipuProvider(LLMProvider):
    """智谱 GLM5 提供商"""

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    MODEL = "glm-5"

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
                        logger.warning(f"智谱 API 触发限流，等待 {retry_after} 秒（第 {attempt+1}/{max_retries} 次重试）")
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = min(60, 10 * (2 ** attempt))
                    logger.warning(f"智谱 API 触发限流，等待 {retry_after} 秒（第 {attempt+1}/{max_retries} 次重试）")
                    await asyncio.sleep(retry_after)
                else:
                    raise
            except httpx.ReadTimeout as e:
                if attempt < max_retries - 1:
                    retry_after = min(60, 30 * (2 ** attempt))
                    logger.warning(f"智谱 API 读取超时，等待 {retry_after} 秒后重试（第 {attempt+1}/{max_retries} 次）")
                    await asyncio.sleep(retry_after)
                else:
                    raise RuntimeError(f"智谱 API 调用失败：超过最大重试次数（最后错误：读取超时）")
        raise RuntimeError("智谱 API 调用失败：超过最大重试次数")

    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        prompt = COMPILE_PROMPT.format(
            notes="\n\n".join(notes),
            existing_wiki="\n\n".join(existing_wiki) if existing_wiki else "无",
        )
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature=0.7)

    async def digest_note(self, content: str) -> DigestResult:
        """消化单条笔记：生成标题、分类、标签"""
        prompt = DIGEST_PROMPT.format(content=content[:4000])  # 限制内容长度
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.chat(messages, temperature=0.3)
            # 解析 JSON 响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            result = json.loads(response)
            return DigestResult(
                title=result.get("title", "未命名笔记")[:50],  # 限制标题长度
                category=result.get("category", "未分类"),
                confidence=result.get("confidence", "low"),
                tags=result.get("tags", [])
            )
        except Exception as e:
            logger.error(f"解析 digest 响应失败：{e}")
            # 降级处理
            return DigestResult(
                title=f"笔记_{content[:20]}",
                category="未分类",
                confidence="low",
                tags=[]
            )
