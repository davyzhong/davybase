# src/extractor.py
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Optional
import httpx
import logging

logger = logging.getLogger("davybase.extractor")

class GetNoteClient:
    """get 笔记 API 客户端"""

    BASE_URL = "https://openapi.biji.com"

    def __init__(self, api_key: str, client_id: str):
        self.api_key = api_key
        self.client_id = client_id
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": self.api_key,
                "X-Client-ID": self.client_id
            },
            timeout=30.0
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def _get(self, path: str, params: dict = None) -> dict:
        # 速率限制：请求间隔 >= 1 秒
        await asyncio.sleep(1.0)

        # 429 限流重试策略
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._client.get(path, params=params)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"触发限流，等待 {retry_after} 秒")
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    logger.warning(f"触发限流，等待 {retry_after} 秒")
                    await asyncio.sleep(retry_after)
                else:
                    raise

    async def list_knowledge_bases(self) -> list:
        """获取知识库列表"""
        result = await self._get("/open/api/v1/resource/knowledge/list", {"page": 1})
        return result.get("data", {}).get("topics", [])

    async def list_knowledge_notes(self, topic_id: str, page: int = 1) -> tuple[list, bool]:
        """获取知识库笔记列表，返回 (notes, has_more)"""
        result = await self._get("/open/api/v1/resource/knowledge/notes", {
            "topic_id": topic_id,
            "page": page
        })
        data = result.get("data", {})
        return data.get("notes", []), data.get("has_more", False)

    async def get_note_detail(self, note_id: str) -> dict:
        """获取笔记详情"""
        result = await self._get("/open/api/v1/resource/note/detail", {"id": note_id})
        return result.get("data", {}).get("note", {})

class Extractor:
    """笔记抽取器"""

    def __init__(self, api_key: str, client_id: str, data_dir: str):
        self.api_key = api_key
        self.client_id = client_id
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.failed_dir = self.data_dir / "_failed"

    async def run(self):
        """执行抽取"""
        logger.info("开始抽取笔记")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

        async with GetNoteClient(self.api_key, self.client_id) as client:
            kbs = await client.list_knowledge_bases()
            logger.info(f"发现 {len(kbs)} 个知识库")

            for kb in kbs:
                await self._extract_knowledge_base(client, kb)

            await self._extract_inbox_notes(client)

        logger.info("抽取完成")

    async def _extract_knowledge_base(self, client: GetNoteClient, kb: dict):
        """抽取单个知识库"""
        kb_name = kb["name"]
        kb_dir = self.raw_dir / kb_name
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "attachments").mkdir(exist_ok=True)

        logger.info(f"抽取知识库 \"{kb_name}\"")

        page = 1
        has_more = True
        while has_more:
            notes, has_more = await client.list_knowledge_notes(kb["topic_id"], page)
            logger.info(f"  第{page}页：{len(notes)} 条笔记")

            for note in notes:
                await self._extract_note(client, note, kb_dir, kb_name)

            page += 1
            if has_more:
                await asyncio.sleep(1.0)

    async def _extract_note(self, client: GetNoteClient, note: dict, kb_dir: Path, kb_name: str):
        """抽取单条笔记"""
        note_id = note["note_id"]

        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.5)

            content = self._format_note_content(detail)

            note_file = kb_dir / f"{note_id}.md"
            note_file.write_text(content, encoding="utf-8")

            logger.debug(f"  保存笔记 {note_id}: {detail.get('title', '无标题')}")

        except Exception as e:
            logger.error(f"  抽取笔记 {note_id} 失败：{e}")
            self._save_failed_note(note, str(e))

    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        lines = [
            "---",
            f"note_id: {detail.get('note_id', '')}",
            f"note_type: {detail.get('note_type', '')}",
            f"created_at: {detail.get('created_at', '')}",
            f"tags: {detail.get('tags', [])}",
            "---",
            "",
            f"# {detail.get('title', '无标题')}",
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

    def _save_failed_note(self, note: dict, error: str):
        """保存失败的笔记"""
        failed_file = self.failed_dir / f"{note['note_id']}.json"
        failed_file.write_text(json.dumps({
            "note": note,
            "error": error
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _extract_inbox_notes(self, client: GetNoteClient):
        """抽取散落笔记（不在任何知识库中）"""
        inbox_dir = self.raw_dir / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info("抽取散落笔记")
