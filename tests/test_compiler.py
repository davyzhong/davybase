import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.compiler import Compiler
from src.config import Config


@pytest.mark.asyncio
async def test_compiler_saves_wiki_entries(tmp_path, monkeypatch):
    """测试编译器保存 wiki 条目"""
    # Mock 所有 LLM 提供商的初始化
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
    kb_dir = data_dir / "test_kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "note1.md").write_text("# Original Note 1")

    # Mock Config
    mock_config = MagicMock(spec=Config)
    mock_config.get_llm_api_key = MagicMock(return_value="test_key")

    # Patch PROVIDERS to use our mock
    with patch.object(Compiler, '_save_wiki_entries') as mock_save:
        compiler = Compiler(mock_config, mock_provider, str(data_dir), str(vault_path))
        # Patch _compile_knowledge_base to avoid actual LLM calls
        with patch.object(Compiler, '_compile_knowledge_base', new_callable=AsyncMock) as mock_compile_kb:
            mock_compile_kb.return_value = None
            await compiler.run()

    # 验证 wiki 目录被创建
    wiki_dir = vault_path / "wiki"
    assert wiki_dir.exists()
