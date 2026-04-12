import pytest
from unittest.mock import AsyncMock
from src.compiler import Compiler


@pytest.mark.asyncio
async def test_compiler_saves_wiki_entries(tmp_path):
    mock_provider = AsyncMock()
    mock_provider.compile_notes.return_value = """---ENTRY---
# 测试概念

%%davybase-auto-begin%%
## 摘要
这是摘要。
%%davybase-auto-end%%
"""
    vault_path = tmp_path / "vault"
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw" / "test_kb"
    raw_dir.mkdir(parents=True)
    (raw_dir / "note1.md").write_text("# Original Note 1")
    compiler = Compiler(mock_provider, str(data_dir), str(vault_path))
    await compiler.run()

    wiki_dir = vault_path / "wiki"
    assert (wiki_dir / "测试概念.md").exists()
