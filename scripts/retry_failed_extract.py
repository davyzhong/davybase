#!/usr/bin/env python3
"""
重新抽取失败的笔记
支持重试多次失败的笔记
"""
import asyncio
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.extractor import GetNoteClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("davybase.retry_failed")


class RetryFailedExtractor:
    """失败笔记重抽器"""

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.data_path)
        self.inbox_dir = self.data_dir / "_inbox"
        self.failed_dir = self.data_dir / "_failed"
        self.progress_file = self.failed_dir / ".retry_progress.json"

    def load_failed_notes(self) -> list:
        """加载失败的笔记"""
        failed = []
        for json_file in self.failed_dir.glob("*.json"):
            if json_file.name.startswith("."):
                continue
            try:
                data = json.loads(json_file.read_text(encoding='utf-8'))
                note_id = data.get("note", {}).get("note_id") or data.get("note", {}).get("id")
                if note_id:
                    failed.append({
                        "note_id": str(note_id),
                        "file": str(json_file),
                        "error": data.get("error", "unknown")
                    })
            except Exception as e:
                logger.error(f"读取失败文件失败 {json_file}: {e}")
        return failed

    def save_progress(self, processed_ids: set):
        """保存处理进度"""
        self.progress_file.write_text(
            json.dumps({"processed_ids": list(processed_ids)}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def load_progress(self) -> set:
        """加载已处理的笔记 ID"""
        if self.progress_file.exists():
            data = json.loads(self.progress_file.read_text(encoding='utf-8'))
            return set(data.get("processed_ids", []))
        return set()

    async def run(self, max_retries: int = 3):
        """执行重试"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 加载进度
        processed_ids = self.load_progress()
        logger.info(f"已从进度恢复：已处理 {len(processed_ids)} 条")

        # 加载失败的笔记
        failed_notes = self.load_failed_notes()
        logger.info(f"失败笔记总数：{len(failed_notes)} 条")

        # 过滤已处理的
        pending = [n for n in failed_notes if n["note_id"] not in processed_ids]
        logger.info(f"待重试：{len(pending)} 条")

        if not pending:
            logger.info("没有待重试的笔记")
            return

        # 检查 inbox 中是否已存在
        inbox_ids = self._get_inbox_ids()
        already_exists = [n for n in pending if n["note_id"] in inbox_ids]
        if already_exists:
            logger.info(f"已在 inbox 中存在：{len(already_exists)} 条，跳过")
            for n in already_exists:
                processed_ids.add(n["note_id"])
                self.save_progress(processed_ids)
            pending = [n for n in pending if n["note_id"] not in inbox_ids]
            logger.info(f"剩余待重试：{len(pending)} 条")

        if not pending:
            logger.info("没有待重试的笔记")
            return

        async with GetNoteClient(
            *self.config.get_getnote_credentials()
        ) as client:
            success_count = 0
            failed_count = 0

            for i, note in enumerate(pending, 1):
                note_id = note["note_id"]
                logger.info(f"[{i}/{len(pending)}] 重试笔记 {note_id} (原错误：{note['error']})")

                success = await self._retry_extract(client, note_id, max_retries)

                if success:
                    success_count += 1
                    processed_ids.add(note_id)
                    self.save_progress(processed_ids)
                    # 删除已成功的失败文件
                    failed_file = self.failed_dir / f"{note_id}.json"
                    if failed_file.exists():
                        failed_file.unlink()
                        logger.info(f"  成功，已删除失败文件")
                else:
                    failed_count += 1
                    logger.warning(f"  仍然失败")

                await asyncio.sleep(2.0)  # 增加间隔避免限流

            logger.info(f"\n完成：成功 {success_count} 条，失败 {failed_count} 条")

    def _get_inbox_ids(self) -> set:
        """获取 inbox 中已有的笔记 ID"""
        inbox_ids = set()
        if self.inbox_dir.exists():
            for md_file in self.inbox_dir.glob("*.md"):
                parts = md_file.stem.split("_", 1)
                if parts:
                    inbox_ids.add(parts[0])
        return inbox_ids

    async def _retry_extract(self, client: GetNoteClient, note_id: str, max_retries: int) -> bool:
        """重试抽取单条笔记"""
        for attempt in range(max_retries):
            try:
                detail = await client.get_note_detail(note_id)
                await asyncio.sleep(0.5)

                if detail is None:
                    logger.warning(f"  尝试 {attempt + 1}/{max_retries}: 笔记详情返回 None")
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue

                # 格式化笔记内容
                content = self._format_note_content(detail)
                filename = self._sanitize_filename(detail.get('title', '无标题'))

                note_file = self.inbox_dir / f"{note_id}_{filename}.md"
                note_file.write_text(content, encoding='utf-8')

                logger.info(f"  成功保存到 {note_file.name}")
                return True

            except Exception as e:
                logger.error(f"  尝试 {attempt + 1}/{max_retries} 失败：{e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避

        return False

    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容为 Markdown"""
        title = detail.get('title', '')
        if not title:
            content = detail.get("content", "")
            first_line = content.split('\n')[0].strip()[:50]
            title = first_line if first_line and first_line != '#' else str(detail.get('note_id', '无标题'))

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

    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()[:80]


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="重新抽取失败的笔记")
    parser.add_argument("--max-retries", type=int, default=3, help="最大重试次数")
    args = parser.parse_args()

    config = Config()
    extractor = RetryFailedExtractor(config)
    await extractor.run(max_retries=args.max_retries)


if __name__ == "__main__":
    asyncio.run(main())
