#!/usr/bin/env python3
"""
快速检查：get 笔记 API 中是否有新的增量笔记
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import GetNoteClient
from src.config import Config


async def main():
    config = Config()
    vault = Path(config.vault_path)
    api_key, client_id = config.get_getnote_credentials()

    # 1. 已抽取 ID
    progress = vault / ".davybase" / "progress" / ".inbox_extract_progress.json"
    with open(progress) as f:
        extracted_ids = set(json.load(f).get('extracted_ids', []))
    print(f"本地已抽取 ID：{len(extracted_ids):,} 条")

    # 2. 基准线
    import sqlite3
    conn = sqlite3.connect(str(vault / ".davybase" / "sync_state.db"))
    row = conn.execute("SELECT last_sync_at, notes_extracted FROM incremental_sync_state WHERE id=1").fetchone()
    conn.close()
    baseline = row[0] if row else "无"
    print(f"基准线时间：{baseline}")

    # 3. API 获取所有笔记 ID
    print("\n正在从 API 获取笔记...")
    async with GetNoteClient(api_key=api_key, client_id=client_id, rate_limit_delay=0.5) as client:
        # 知识库笔记
        kb_ids = set()
        kbs = await client.list_knowledge_bases()
        for kb in kbs:
            page = 1
            while True:
                notes, has_more = await client.list_knowledge_notes(kb['id'], page=page)
                for n in notes:
                    kb_ids.add(n.get('note_id'))
                if not has_more:
                    break
                page += 1
                await asyncio.sleep(0.5)
        print(f"API 知识库笔记：{len(kb_ids):,} 条")

        # 散落笔记
        inbox_notes = await client.list_all_notes()
        inbox_ids = set(n.get('note_id') for n in inbox_notes)
        print(f"API 散落笔记：{len(inbox_ids):,} 条")

    # 4. 汇总
    all_api_ids = kb_ids | inbox_ids
    new_ids = all_api_ids - extracted_ids

    print(f"\n=== 检查结果 ===")
    print(f"API 笔记总数：{len(all_api_ids):,} 条")
    print(f"本地已抽取：{len(extracted_ids):,} 条")
    print(f"新增（未抽取）：{len(new_ids):,} 条")

    if new_ids:
        print(f"\n新增笔记 ID (前 20 条):")
        for i, nid in enumerate(list(new_ids)[:20], 1):
            print(f"  {i}. {nid}")
    else:
        print(f"\n✅ 没有新增笔记，所有 get 笔记都已同步到本地")

    # 5. 保存新增 ID（如果有）
    if new_ids:
        output = vault / ".davybase" / "new_note_ids_latest.json"
        with open(output, 'w') as f:
            json.dump(list(new_ids), f, indent=2)
        print(f"\n新增笔记 ID 已保存到：{output}")


if __name__ == "__main__":
    asyncio.run(main())
