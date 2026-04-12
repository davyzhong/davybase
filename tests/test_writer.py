# tests/test_writer.py
import pytest
from pathlib import Path
from src.writer import Writer


@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "wiki").mkdir()
    return vault


def test_writer_creates_new_entry(temp_vault):
    writer = Writer(str(temp_vault))
    content = """---
title: 新概念
---

# 新概念

%%davybase-auto-begin%%
摘要内容
%%davybase-auto-end%%
"""
    writer.write(content)
    assert (temp_vault / "wiki" / "新概念.md").exists()


def test_writer_preserves_manual_edits(temp_vault):
    writer = Writer(str(temp_vault))

    # 首次写入
    writer.write("""---
title: 现有概念
---

# 现有概念

%%davybase-auto-begin%%
旧摘要
%%davybase-auto-end%%

## 手动部分
这是手动编辑的内容。
""")

    # 再次写入（更新 auto 块）
    writer.write("""---
title: 现有概念
---

# 现有概念

%%davybase-auto-begin%%
新摘要
%%davybase-auto-end%%
""")

    content = (temp_vault / "wiki" / "现有概念.md").read_text()
    assert "新摘要" in content
    assert "手动部分" in content
    assert "这是手动编辑的内容" in content
