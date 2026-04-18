#!/usr/bin/env python3
"""
直接抓取 1,173 条遗漏的散落笔记到本地
只获取这些笔记的详情，不遍历全部 API 笔记
"""
import asyncio
import json
import hashlib
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import GetNoteClient
from src.config import Config


async def main():
    config = Config()
    vault = Path(config.vault_path)
    api_key, client_id = config.get_getnote_credentials()

    # 1. 读取 1,173 条遗漏的笔记 ID
    new_ids_file = vault / ".davybase" / "new_note_ids.json"
    with open(new_ids_file) as f:
        new_ids = json.load(f)

    print(f"遗漏笔记数量：{len(new_ids):,} 条")
    print(f"目标目录：{vault}/raw/notes/_inbox/")
    print()

    # 2. 输出目录
    inbox_dir = vault / "raw" / "notes" / "_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    # 3. 加载已有进度
    progress_file = vault / ".davybase" / "progress" / ".inbox_extract_progress.json"
    if progress_file.exists():
        with open(progress_file) as f:
            progress = json.load(f)
        extracted_ids = set(progress.get('extracted_ids', []))
    else:
        progress = {'extracted_ids': []}
        extracted_ids = set()

    print(f"已抽取笔记 ID：{len(extracted_ids):,} 条")

    # 4. 开始抓取
    success = 0
    failed = 0
    skipped = 0

    async with GetNoteClient(api_key=api_key, client_id=client_id, rate_limit_delay=0.5) as client:
        for i, note_id in enumerate(new_ids, 1):
            # 跳过已抽取的
            if note_id in extracted_ids:
                skipped += 1
                continue

            try:
                # 获取笔记详情
                note = await client.get_note_detail(note_id)

                if not note:
                    print(f"  [{i}/{len(new_ids)}] {note_id} - 详情为空，跳过")
                    failed += 1
                    continue

                title = note.get('title', 'untitled')
                content = note.get('content', '') or note.get('markdown_content', '') or note.get('text', '')

                if not content:
                    print(f"  [{i}/{len(new_ids)}] {note_id} - 无内容，跳过")
                    failed += 1
                    continue

                # 生成安全的文件名
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.', '（', '）', '，', '。', '、')).strip()
                if not safe_title:
                    safe_title = f"note_{note_id}"
                safe_title = safe_title[:80]  # 限制长度

                filename = f"{safe_title}.md"
                filepath = inbox_dir / filename

                # 避免文件名冲突
                if filepath.exists():
                    filename = f"{safe_title}_{note_id[:8]}.md"
                    filepath = inbox_dir / filename

                # 写入文件
                # 添加 frontmatter
                frontmatter = f"""---
note_id: {note_id}
source: getnote
created_at: {note.get('created_at', '')}
extracted_at: {datetime.now().isoformat()}
---

"""
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(frontmatter + content)

                # 更新进度
                extracted_ids.add(note_id)
                success += 1

                if i % 10 == 0 or i == len(new_ids):
                    print(f"  [{i}/{len(new_ids)}] 成功 {success} | 失败 {failed} | 跳过 {skipped}")

                # 每 50 条保存一次进度
                if i % 50 == 0:
                    progress['extracted_ids'] = list(extracted_ids)
                    with open(progress_file, 'w', encoding='utf-8') as f:
                        json.dump(progress, f, ensure_ascii=False)
                    print(f"  → 进度已保存 ({len(extracted_ids):,} 条)")

            except Exception as e:
                print(f"  [{i}/{len(new_ids)}] {note_id} - 错误：{e}")
                failed += 1
                # 出错后等久一点
                await asyncio.sleep(5)

    # 5. 保存最终进度
    progress['extracted_ids'] = list(extracted_ids)
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False)

    print(f"\n=== 抓取完成 ===")
    print(f"总计：{len(new_ids):,} 条")
    print(f"成功：{success:,} 条")
    print(f"失败：{failed:,} 条")
    print(f"跳过（已存在）：{skipped:,} 条")
    print(f"已抽取笔记 ID 总数：{len(extracted_ids):,} 条")
    print(f"进度文件已更新：{progress_file}")


if __name__ == "__main__":
    asyncio.run(main())
