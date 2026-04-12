#!/usr/bin/env python3
"""
快速恢复抽取脚本 - 绕过 list_all_notes 限流
直接从已抽取的文件恢复，只获取缺失的笔记
"""
import asyncio
import json
import logging
from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.extractor import GetNoteClient
from src.sync_state import SyncState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("davybase.fast_extract")


class FastResumeExtractor:
    """快速恢复抽取器"""

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.data_path)
        self.inbox_dir = self.data_dir / "_inbox"
        self.progress_file = self.data_dir / ".inbox_extract_progress.json"
        self.state = SyncState(f"{self.data_dir}/sync.db")

    def load_existing_note_ids(self) -> set:
        """从 inbox 文件和进度文件加载已抽取的 note_id"""
        note_ids = set()

        # 从进度文件加载
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                note_ids.update(str(id) for id in data.get("extracted_ids", []))
            logger.info(f"从进度文件恢复：{len(note_ids)} 条")

        # 从 inbox 文件扫描（防止并行处理时进度未保存）
        for md_file in self.inbox_dir.glob("*.md"):
            if md_file.name == ".md":  # 跳过空文件名
                continue
            content = md_file.read_text(encoding='utf-8')
            for line in content.split('\n')[:10]:
                if line.startswith('note_id:'):
                    note_id = line.split(':')[1].strip()
                    if note_id and note_id.isdigit():
                        note_ids.add(note_id)
                    break

        logger.info(f"从 inbox 文件扫描后总计：{len(note_ids)} 条")
        return note_ids

    def get_scattered_note_ids(self, all_notes: list, raw_synced_ids: set, extracted_ids: set) -> list:
        """获取散落笔记 ID 列表"""
        return [
            n for n in all_notes
            if str(n["note_id"]) not in raw_synced_ids
            and str(n["note_id"]) not in extracted_ids
        ]

    async def run(self):
        """执行批量抽取"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 加载已抽取的 ID
        extracted_ids = self.load_existing_note_ids()

        # 获取已同步的笔记 ID
        raw_synced_ids = self._get_raw_synced_ids()
        logger.info(f"raw 目录已同步：{len(raw_synced_ids)} 条")

        async with GetNoteClient(*self.config.get_getnote_credentials()) as client:
            # 获取所有笔记列表（可能需要等待限流）
            logger.info("正在获取笔记列表...（如触发限流请耐心等待）")
            try:
                all_notes = await client.list_all_notes()
                logger.info(f"全部笔记：{len(all_notes)} 条")
            except Exception as e:
                logger.error(f"获取笔记列表失败：{e}")
                logger.info("使用备用策略：从 progress 文件继续")
                return

            # 计算待抽取的散落笔记
            inbox_notes = self.get_scattered_note_ids(all_notes, raw_synced_ids, extracted_ids)
            logger.info(f"待抽取散落笔记：{len(inbox_notes)} 条")

            if not inbox_notes:
                logger.info("✅ 没有待抽取的笔记，全部已完成！")
                return

            # 串行抽取（避免限流）
            for i, note in enumerate(inbox_notes, 1):
                logger.info(f"\n[{i}/{len(inbox_notes)}] 抽取 {note['note_id']}...")
                success = await self._extract_note(client, note)
                if success:
                    extracted_ids.add(str(note["note_id"]))
                    # 每条保存进度
                    self._save_progress(extracted_ids)

                # 单条间隔 2 秒
                await asyncio.sleep(2.0)

        logger.info(f"\n✅ 抽取完成，共 {len(extracted_ids)} 条笔记")

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

    async def _extract_note(self, client: GetNoteClient, note: dict) -> bool:
        """抽取单条笔记"""
        note_id = note["note_id"]
        try:
            detail = await client.get_note_detail(note_id)
            await asyncio.sleep(0.5)

            content = self._format_note_content(detail)
            filename = self._sanitize_filename(detail.get('title', '无标题'))

            note_file = self.inbox_dir / f"{note_id}_{filename}.md"
            note_file.write_text(content, encoding='utf-8')

            logger.info(f"  ✅ {note_id}")
            return True

        except Exception as e:
            logger.error(f"  ❌ {note_id}: {e}")
            self._save_failed_note(note, str(e))
            return False

    def _format_note_content(self, detail: dict) -> str:
        """格式化笔记内容"""
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

    def _save_progress(self, extracted_ids: set):
        """保存进度"""
        self.progress_file.write_text(
            json.dumps({"extracted_ids": list(extracted_ids)}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

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
    config = Config()
    extractor = FastResumeExtractor(config)
    await extractor.run()


if __name__ == "__main__":
    asyncio.run(main())
