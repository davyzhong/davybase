# src/writer.py
import hashlib
import re
import subprocess
import json
from pathlib import Path
import httpx
import logging

logger = logging.getLogger("davybase.writer")


class Writer:
    """Obsidian vault 写入器

    支持两种写入模式：
    1. 文件系统模式（默认）- 直接写入 .md 文件
    2. CLI 模式 - 通过 Obsidian CLI API 写入（需要 Obsidian 应用运行）

    模式选择：
    - 如果检测到 Obsidian 应用运行且 vault 已打开，使用 CLI 模式
    - 否则回退到文件系统模式
    """

    def __init__(self, vault_path: str, use_cli: bool = True):
        self.vault_path = Path(vault_path)
        self.wiki_dir = self.vault_path / "wiki"
        self.attachments_dir = self.wiki_dir / "attachments"
        self.use_cli = use_cli
        self._obsidian_available = None  # 缓存 Obsidian 可用性检查结果

    def _check_obsidian_available(self) -> bool:
        """检查 Obsidian CLI 是否可用"""
        if self._obsidian_available is not None:
            return self._obsidian_available

        try:
            # 尝试运行 obsidian help 检查 CLI 是否可用
            result = subprocess.run(
                ["obsidian", "help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self._obsidian_available = (result.returncode == 0)
            if self._obsidian_available:
                logger.info("Obsidian CLI 可用，将使用 CLI 模式写入")
            else:
                logger.info("Obsidian CLI 不可用，使用文件系统模式")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._obsidian_available = False
            logger.info("Obsidian CLI 未找到，使用文件系统模式")

        return self._obsidian_available

    def write(self, content: str):
        """写入 wiki 条目

        自动选择最佳写入方式：
        1. 如果 Obsidian CLI 可用，使用 CLI 模式（支持实时刷新、属性管理）
        2. 否则使用文件系统模式（直接写入文件）
        """
        title = self._extract_title(content)
        if not title:
            logger.warning("无法提取标题，跳过")
            return

        # 尝试使用 CLI 模式
        if self.use_cli and self._check_obsidian_available():
            if self._write_cli(content, title):
                return

        # 回退到文件系统模式
        self._write_filesystem(content, title)

    def _write_cli(self, content: str, title: str) -> bool:
        """使用 Obsidian CLI 写入

        优势：
        - 实时刷新 Obsidian 界面
        - 自动设置属性（properties）
        - 支持标签管理
        - 触发 Obsidian 插件钩子

        返回：True 表示成功，False 表示需要回退到文件系统模式
        """
        try:
            filename = self._sanitize_filename(title)
            file_path = f"wiki/{filename}.md"

            # 检查文件是否已存在
            check_result = subprocess.run(
                ["obsidian", "read", f"file={filename}", "path=wiki/{filename}.md", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if check_result.returncode == 0:
                # 文件已存在，使用 append/replace 模式
                # 提取 auto 块内容
                auto_content = self._extract_auto_block(content)
                if auto_content:
                    # 更新现有文件
                    result = subprocess.run(
                        ["obsidian", "write", f"path={file_path}", f"content={content}", "overwrite"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        logger.info(f"[CLI] 更新 wiki 条目：{title}")
                        return True

            # 新文件，使用 create
            result = subprocess.run(
                ["obsidian", "create", f"name={title}", f"path=wiki/{filename}.md", f"content={content}", "silent"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"[CLI] 创建 wiki 条目：{title}")
                return True
            else:
                logger.warning(f"[CLI] 创建失败：{result.stderr}，回退到文件系统模式")
                return False

        except subprocess.TimeoutExpired:
            logger.warning("[CLI] 命令超时，回退到文件系统模式")
            return False
        except Exception as e:
            logger.warning(f"[CLI] 执行失败：{e}，回退到文件系统模式")
            return False

    def _write_filesystem(self, content: str, title: str):
        """文件系统模式写入 wiki 条目"""
        file_path = self.wiki_dir / f"{self._sanitize_filename(title)}.md"

        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            if self._is_auto_block_changed(existing, content):
                content = self._merge_content(existing, content)
            else:
                logger.debug(f"条目 {title} 无变更，跳过")
                return

        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"写入 wiki 条目：{title}")

    def _extract_title(self, content: str) -> str:
        """提取 frontmatter 中的 title"""
        match = re.search(r"^---\s*\n.*?title:\s*(.+?)\s*\n", content, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return None

    def _sanitize_filename(self, title: str) -> str:
        """文件名安全化"""
        for char in ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]:
            title = title.replace(char, "_")
        return title.strip()

    def _is_auto_block_changed(self, existing: str, new: str) -> bool:
        """检查 auto 块是否有变更"""
        old_block = self._extract_auto_block(existing)
        new_block = self._extract_auto_block(new)
        return old_block != new_block

    def _extract_auto_block(self, content: str) -> str:
        """提取 auto 块内容"""
        match = re.search(
            r"%%davybase-auto-begin%%(.*?)%%davybase-auto-end%%",
            content,
            re.DOTALL
        )
        return match.group(1).strip() if match else ""

    def _merge_content(self, existing: str, new: str) -> str:
        """合并现有内容和新的 auto 块"""
        manual_part = re.sub(
            r"%%davybase-auto-begin%%.*?%%davybase-auto-end%%",
            "",
            existing,
            flags=re.DOTALL
        )

        new_auto_match = re.search(
            r"(%%davybase-auto-begin%%.*?%%davybase-auto-end%%)",
            new,
            re.DOTALL
        )
        new_auto = new_auto_match.group(1) if new_auto_match else ""

        return new_auto + "\n" + manual_part.strip()

    async def download_image(self, url: str, note_id: str) -> str:
        """下载图片到本地，返回本地路径"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            filename = f"{note_id}_{url.split('/')[-1]}"
            image_path = self.attachments_dir / filename
            image_path.write_bytes(response.content)

            return f"attachments/{filename}"
