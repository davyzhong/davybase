#!/usr/bin/env python3
"""
散落笔记批量抽取脚本
支持断点续传和进度跟踪
"""
import asyncio
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.extractor import GetNoteClient
from src.sync_state import SyncState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("davybase.batch_extract")


class BatchInboxExtractor:
    """散落笔记批量抽取器"""

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.data_path)
        self.inbox_dir = self.data_dir / "_inbox"
        self.progress_file = self.data_dir / ".inbox_extract_progress.json"
        self.state = SyncState(f"{self.data_dir}/sync.db")

    def load_progress(self) -> set:
        """加载已抽取的笔记 ID"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(str(id) for id in data.get("extracted_ids", []))
        return set()

    def save_progress(self, extracted_ids: set):
        """保存抽取进度"""
        self.progress_file.write_text(
            json.dumps({"extracted_ids": list(extracted_ids)}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        logger.info(f"进度已保存：{len(extracted_ids)} 条笔记")

    def _get_raw_synced_ids(self) -> set:
        """获取 raw 目录中已同步的笔记 ID"""
        synced_ids = set()
        for kb_dir in self.data_dir.iterdir():
            if kb_dir.is_dir() and kb_dir.name not in ("_inbox", "_failed"):
                for md_file in kb_dir.glob("*.md"):
                    try:
                        content = md_file.read_text(encoding='utf-8')
                        for line in content.split('\n'):
                            if line.startswith('note_id:'):
                                synced_ids.add(line.split(':')[1].strip())
                    except Exception:
                        continue
        return synced_ids

    async def run(self, limit: int = None):
        """执行批量抽取"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 加载进度
        extracted_ids = self.load_progress()
        logger.info(f"已从进度恢复：已抽取 {len(extracted_ids)} 条笔记")

        # 获取已同步的笔记 ID
        raw_synced_ids = self._get_raw_synced_ids()
        logger.info(f"raw 目录已同步：{len(raw_synced_ids)} 条")

        async with GetNoteClient(
            *self.config.get_getnote_credentials()
        ) as client:
            # 获取所有笔记
            logger.info("正在获取笔记列表...")
            all_notes = await client.list_all_notes()
            logger.info(f"全部笔记：{len(all_notes)} 条")

            # 计算待抽取的散落笔记
            inbox_notes = [
                n for n in all_notes
                if str(n["note_id"]) not in raw_synced_ids
                and str(n["note_id"]) not in extracted_ids
            ]

            if limit:
                inbox_notes = inbox_notes[:limit]
                logger.info(f"限制模式：仅处理前 {limit} 条")

            logger.info(f"待抽取散落笔记：{len(inbox_notes)} 条")

            if not inbox_notes:
                logger.info("没有待抽取的笔记")
                return

            # 批量抽取（并行处理）
            batch_size = 50  # 减小批次大小
            total_batches = (len(inbox_notes) + batch_size - 1) // batch_size
            semaphore = asyncio.Semaphore(5)  # 降低并发：最多 5 个并发请求

            async def extract_with_semaphore(note):
                async with semaphore:
                    result = await self._extract_note(client, note)
                    if result:
                        extracted_ids.add(str(note["note_id"]))
                    return result

            for i in range(0, len(inbox_notes), batch_size):
                batch = inbox_notes[i:i+batch_size]
                batch_num = i // batch_size + 1
                logger.info(f"\n抽取批次 {batch_num}/{total_batches} (本批 {len(batch)} 条)")

                # 并发处理批次
                tasks = [extract_with_semaphore(note) for note in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 统计成功/失败
                success_count = sum(1 for r in results if r is True)
                failed_count = sum(1 for r in results if r is False or isinstance(r, Exception))

                extracted_ids.update(str(note["note_id"]) for note, r in zip(batch, results) if r is True)

                # 保存进度
                self.save_progress(extracted_ids)
                logger.info(f"  进度：{len(extracted_ids)}/{len(inbox_notes)} (本批成功：{success_count}, 失败：{failed_count})")

                # 批次间隔（降低限流风险）
                await asyncio.sleep(3.0)  # 增加批次间隔

        # 保存最终进度
        self.save_progress(extracted_ids)
        logger.info(f"\n✅ 抽取完成，共 {len(extracted_ids)} 条笔记")

    async def _extract_note(self, client: GetNoteClient, note: dict) -> bool:
        """抽取单条笔记，成功返回 True，失败返回 False"""
        note_id = note["note_id"]
        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.1)  # 降低延迟

            # 格式化笔记内容
            content = self._format_note_content(detail)
            filename = self._sanitize_filename(detail.get('title', '无标题'))

            note_file = self.inbox_dir / f"{note_id}_{filename}.md"
            note_file.write_text(content, encoding='utf-8')

            logger.debug(f"  ✓ {note_id}")
            return True

        except Exception as e:
            logger.error(f"  ✗ 抽取笔记 {note_id} 失败：{e}")
            self._save_failed_note(note, str(e))
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

    def _save_failed_note(self, note: dict, error: str):
        """保存失败的笔记"""
        failed_dir = self.data_dir / "_failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_file = failed_dir / f"{note['note_id']}.json"
        failed_file.write_text(json.dumps({
            "note": note,
            "error": error
        }, ensure_ascii=False, indent=2), encoding='utf-8')


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="批量抽取散落笔记")
    parser.add_argument("--limit", type=int, help="限制处理数量（测试用）")
    parser.add_argument("--resume", action="store_true", help="从中断处恢复")
    args = parser.parse_args()

    config = Config()
    extractor = BatchInboxExtractor(config)
    await extractor.run(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
