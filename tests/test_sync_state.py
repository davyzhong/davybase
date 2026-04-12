# tests/test_sync_state.py
import pytest
from pathlib import Path
from src.sync_state import SyncState

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    state = SyncState(str(db_path))
    yield state
    state.close()

def test_insert_and_get_note(temp_db):
    temp_db.insert_note("12345", "plain_text", "TestKB", "/raw/TestKB/12345.md", "abc123")
    note = temp_db.get_note("12345")
    assert note["note_id"] == "12345"
    assert note["note_type"] == "plain_text"
    assert note["content_hash"] == "abc123"

def test_update_note_error(temp_db):
    temp_db.insert_note("12345", "plain_text", "TestKB", "/raw/TestKB/12345.md", "abc123")
    temp_db.update_note_error("12345", "API timeout")
    note = temp_db.get_note("12345")
    assert note["error"] == "API timeout"

def test_get_failed_notes(temp_db):
    temp_db.insert_note("1", "plain_text", "KB1", "/raw/1.md", "h1")
    temp_db.update_note_error("1", "error1")
    temp_db.insert_note("2", "plain_text", "KB1", "/raw/2.md", "h2")
    failed = temp_db.get_failed_notes()
    assert len(failed) == 1
    assert failed[0]["note_id"] == "1"

def test_record_sync_run(temp_db):
    run_id = temp_db.record_sync_run("full", "zhipu")
    temp_db.complete_sync_run(run_id, 100, 50, 2)
    # Just verify it doesn't raise

def test_get_status(temp_db):
    temp_db.insert_note("1", "plain_text", "KB1", "/raw/1.md", "h1")
    temp_db.insert_note("2", "plain_text", "KB2", "/raw/2.md", "h2")
    temp_db.update_note_error("1", "error")
    status = temp_db.get_status()
    assert status["total_notes"] == 2
    assert status["failed_count"] == 1
