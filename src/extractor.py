# src/extractor.py
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Optional
import httpx
import logging
from .config import Config

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

    async def list_all_notes(self) -> list:
        """获取全部笔记列表（包括不在知识库中的散落笔记）"""
        all_notes = []
        next_cursor = 0

        while True:
            result = await self._get("/open/api/v1/resource/note/list", {"since_id": next_cursor})
            notes = result.get("data", {}).get("notes", [])
            all_notes.extend(notes)

            has_more = result.get("data", {}).get("has_more", False)
            if not has_more:
                break

            next_cursor = result.get("data", {}).get("next_cursor", 0)
            logger.info(f"已获取 {len(all_notes)} 条笔记...")
            await asyncio.sleep(1.0)

        logger.info(f"共获取 {len(all_notes)} 条笔记")
        return all_notes

class Extractor:
    """笔记抽取器"""

    def __init__(self, config: Config, data_dir: str):
        self.config = config
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir  # 直接使用 data_dir 作为原始 Markdown 存储目录
        self.failed_dir = self.data_dir / "_failed"

        # 从配置获取凭据
        api_key, client_id = self.config.get_getnote_credentials()
        self.api_key = api_key
        self.client_id = client_id

    async def run(self):
        """执行抽取"""
        logger.info("开始抽取笔记")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

        async with GetNoteClient(self.api_key, self.client_id) as client:
            kbs = await client.list_knowledge_bases()
            logger.info(f"发现 {len(kbs)} 个知识库")

            # 收集所有已抽取的笔记 ID
            extracted_note_ids = set()

            for kb in kbs:
                kb_note_ids = await self._extract_knowledge_base(client, kb)
                extracted_note_ids.update(kb_note_ids)

            await self._extract_inbox_notes(client, extracted_note_ids)

        logger.info("抽取完成")

    async def _extract_knowledge_base(self, client: GetNoteClient, kb: dict) -> set:
        """抽取单个知识库，返回抽取的笔记 ID 集合"""
        kb_name = kb["name"]
        kb_dir = self.raw_dir / kb_name
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "attachments").mkdir(exist_ok=True)

        logger.info(f"抽取知识库 \"{kb_name}\"")

        extracted_ids = set()
        page = 1
        has_more = True
        while has_more:
            notes, has_more = await client.list_knowledge_notes(kb["topic_id"], page)
            logger.info(f"  第{page}页：{len(notes)} 条笔记")

            for note in notes:
                await self._extract_note(client, note, kb_dir, kb_name)
                extracted_ids.add(note["note_id"])

            page += 1
            if has_more:
                await asyncio.sleep(1.0)

        return extracted_ids

    async def _extract_note(self, client: GetNoteClient, note: dict, kb_dir: Path, kb_name: str):
        """抽取单条笔记"""
        note_id = note["note_id"]

        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.5)

            content = self._format_note_content(detail)
            filename = self._sanitize_filename(detail.get('title', '无标题'))

            note_file = kb_dir / f"{filename}.md"
            note_file.write_text(content, encoding="utf-8")

            logger.debug(f"  保存笔记 {note_id}: {detail.get('title', '无标题')}")

        except Exception as e:
            logger.error(f"  抽取笔记 {note_id} 失败：{e}")
            self._save_failed_note(note, str(e))

    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化，去除非法字符"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()

    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        # 提取或生成标题
        title = detail.get('title', '')
        if not title:
            # 如果没有标题，尝试从内容中提取第一行
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

    def _save_failed_note(self, note: dict, error: str):
        """保存失败的笔记"""
        failed_file = self.failed_dir / f"{note['note_id']}.json"
        failed_file.write_text(json.dumps({
            "note": note,
            "error": error
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _extract_inbox_notes(self, client: GetNoteClient, extracted_note_ids: set):
        """抽取散落笔记（不在任何知识库中的笔记）"""
        inbox_dir = self.raw_dir / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info("抽取散落笔记")

        # 获取所有笔记
        all_notes = await client.list_all_notes()
        logger.info(f"全部笔记 {len(all_notes)} 条，已抽取 {len(extracted_note_ids)} 条")

        # 过滤出未抽取的笔记
        inbox_notes = [n for n in all_notes if n["note_id"] not in extracted_note_ids]
        logger.info(f"散落笔记 {len(inbox_notes)} 条")

        if not inbox_notes:
            logger.info("  无散落笔记")
            return

        # 抽取散落笔记
        for note in inbox_notes:
            await self._extract_note(client, note, inbox_dir, "_inbox")

        logger.info(f"  完成 {len(inbox_notes)} 条散落笔记抽取")
