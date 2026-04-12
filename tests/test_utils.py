# tests/test_utils.py
import hashlib
import os
from src.utils import compute_hash, setup_logging, LockFile

def test_compute_hash():
    content = "hello world"
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert compute_hash(content) == expected

def test_compute_hash_different_inputs():
    h1 = compute_hash("input1")
    h2 = compute_hash("input2")
    assert h1 != h2

def test_lock_file_acquire_release(tmp_path):
    lock_path = tmp_path / ".test.lock"
    with LockFile(str(lock_path)) as lock:
        assert lock.acquired
        assert lock_path.exists()
    assert not lock_path.exists()

def test_lock_file_blocked_by_existing(tmp_path, monkeypatch):
    lock_path = tmp_path / ".test.lock"
    lock_path.write_text("12345")
    # 模拟 PID 12345 存活
    monkeypatch.setattr(os, "kill", lambda pid, sig: None if pid == 12345 else OSError())
    with LockFile(str(lock_path)) as lock:
        assert not lock.acquired
