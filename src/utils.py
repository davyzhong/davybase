# src/utils.py
import hashlib
import logging
import os
import signal
import sys
from contextlib import ContextDecorator
from pathlib import Path


def compute_hash(content: str) -> str:
    """计算内容的 SHA-256 哈希"""
    return hashlib.sha256(content.encode()).hexdigest()


def setup_logging(log_file: str = None) -> logging.Logger:
    """配置结构化日志"""
    logger = logging.getLogger("davybase")
    logger.setLevel(logging.DEBUG)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s %(levelname)-5s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)

    return logger


class LockFile(ContextDecorator):
    """PID 锁文件，防止并发运行"""

    def __init__(self, path: str):
        self.path = Path(path)
        self.acquired = False
        self.pid = os.getpid()

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self) -> bool:
        if self.path.exists():
            try:
                existing_pid = int(self.path.read_text().strip())
                if self._is_pid_alive(existing_pid):
                    return False
            except (ValueError, PermissionError):
                pass
            # stale lock, remove it
            self.path.unlink()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(str(self.pid))
        self.acquired = True
        return True

    def release(self):
        if self.acquired and self.path.exists():
            try:
                if self.path.read_text().strip() == str(self.pid):
                    self.path.unlink()
            except (FileNotFoundError, PermissionError):
                pass
        self.acquired = False

    def __enter__(self):
        self.acquired = self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
