import pytest
from src.llm_providers.base import LLMProvider
from src.llm_providers.zhipu import ZhipuProvider
from src.llm_providers.minimax import MiniMaxProvider


def test_zhipu_provider_init():
    provider = ZhipuProvider("test_key")
    assert provider.api_key == "test_key"
    assert (
        provider.BASE_URL == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    )


def test_minimax_provider_init():
    provider = MiniMaxProvider("test_key")
    assert provider.api_key == "test_key"
    assert provider.BASE_URL == "https://api.minimaxi.com/v1/chat/completions"
