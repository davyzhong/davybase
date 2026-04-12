# src/sync_state.py
import os
import sqlite3
from datetime import datetime
from typing import Optional


class SyncState:
    """SQLite 同步状态管理"""

    def __init__(self, db_path: str):
        # 确保数据库目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS sync_state (
                note_id TEXT PRIMARY KEY,
                note_type TEXT,
                knowledge_base TEXT,
                raw_path TEXT,
                synced_at DATETIME,
                content_hash TEXT,
                compiled_at DATETIME,
                wiki_path TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT,
                provider TEXT,
                started_at DATETIME,
                completed_at DATETIME,
                notes_extracted INTEGER,
                notes_compiled INTEGER,
                errors INTEGER
            );

            CREATE TABLE IF NOT EXISTS wiki_entries (
                title TEXT PRIMARY KEY,
                source_notes TEXT,
                wiki_hash TEXT,
                created_at DATETIME,
                updated_at DATETIME
            );
        """)
        self.conn.commit()

    def insert_note(self, note_id: str, note_type: str, kb: str, raw_path: str, content_hash: str):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sync_state
            (note_id, note_type, knowledge_base, raw_path, synced_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note_id, note_type, kb, raw_path, datetime.now().isoformat(), content_hash))
        self.conn.commit()

    def get_note(self, note_id: str) -> Optional[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE note_id = ?", (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_note_error(self, note_id: str, error: str):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE sync_state SET error = ? WHERE note_id = ?", (error, note_id))
        self.conn.commit()

    def get_failed_notes(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE error IS NOT NULL")
        return [dict(row) for row in cursor.fetchall()]

    def record_sync_run(self, run_type: str, provider: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sync_runs (run_type, provider, started_at)
            VALUES (?, ?, ?)
        """, (run_type, provider, datetime.now().isoformat()))
        self.conn.commit()
        return cursor.lastrowid

    def complete_sync_run(self, run_id: int, extracted: int, compiled: int, errors: int):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE sync_runs
            SET completed_at = ?, notes_extracted = ?, notes_compiled = ?, errors = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), extracted, compiled, errors, run_id))
        self.conn.commit()

    def get_status(self) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM sync_state")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as failed FROM sync_state WHERE error IS NOT NULL")
        failed = cursor.fetchone()["failed"]

        cursor.execute("SELECT COUNT(*) as wiki FROM wiki_entries")
        wiki = cursor.fetchone()["wiki"]

        cursor.execute("""
            SELECT run_type, provider, completed_at
            FROM sync_runs
            WHERE completed_at IS NOT NULL
            ORDER BY completed_at DESC LIMIT 1
        """)
        last_run = cursor.fetchone()

        return {
            "total_notes": total,
            "failed_count": failed,
            "wiki_entries": wiki,
            "last_run": dict(last_run) if last_run else None
        }

    def close(self):
        self.conn.close()
