# tests/test_extractor.py
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.extractor import Extractor, GetNoteClient

@pytest.fixture
def fixtures():
    with open("tests/fixtures/getnote_responses.json") as f:
        return json.load(f)

@pytest.fixture
def temp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir

def make_mock_response(data):
    """创建模拟的 httpx.Response 对象"""
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response

@pytest.mark.asyncio
async def test_fetch_knowledge_bases(fixtures):
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=make_mock_response(fixtures["knowledge_list"]))
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        async with GetNoteClient("test_key", "test_client_id") as client:
            kbs = await client.list_knowledge_bases()
            assert len(kbs) == 2
            assert kbs[0]["topic_id"] == "kb1"

@pytest.mark.asyncio
async def test_fetch_knowledge_notes(fixtures):
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=make_mock_response(fixtures["knowledge_notes_kb1"]))
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        async with GetNoteClient("test_key", "test_client_id") as client:
            notes, has_more = await client.list_knowledge_notes("kb1")
            assert len(notes) == 3
            assert notes[0]["note_id"] == "1001"

@pytest.mark.asyncio
async def test_extractor_saves_raw_notes(fixtures, temp_data_dir, monkeypatch):
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        # 模拟所有 API 调用：知识库列表 + 2 个知识库的笔记列表 + 3 条笔记详情 + 散落笔记列表
        mock_client.get = AsyncMock(side_effect=[
            make_mock_response(fixtures["knowledge_list"]),
            make_mock_response(fixtures["knowledge_notes_kb1"]),
            make_mock_response(fixtures["note_detail_1001"]),
            make_mock_response(fixtures["note_detail_1002"]),
            make_mock_response(fixtures["note_detail_1003"]),
            make_mock_response(fixtures["knowledge_notes_kb2"]),
            make_mock_response({"data": {"notes": [], "has_more": False}}),  # 散落笔记列表
        ])
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        # Mock Config to return test credentials
        from src.config import Config
        original_init = Config.__init__
        def mock_config_init(self):
            original_init(self)
            self._getnote_api_key = "test_key"
            self._getnote_client_id = "test_client_id"
        monkeypatch.setattr(Config, "__init__", mock_config_init)

        config = Config()
        extractor = Extractor(config, str(temp_data_dir))
        await extractor.run()

        raw_dir = temp_data_dir / "深度学习"
        assert raw_dir.exists()
        assert (raw_dir / "反向传播.md").exists()
        assert (raw_dir / "梯度下降.md").exists()
        assert (raw_dir / "Transformer.md").exists()
