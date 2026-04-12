from abc import ABC, abstractmethod
from typing import TypedDict


class DigestResult(TypedDict):
    """消化结果"""
    title: str
    category: str
    confidence: str
    tags: list[str]


class LLMProvider(ABC):
    """LLM 提供商抽象接口"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送聊天请求，返回响应文本"""
        pass

    @abstractmethod
    async def compile_notes(self, notes: list[str], existing_wiki: list[str]) -> str:
        """编译笔记为 wiki 条目"""
        pass

    @abstractmethod
    async def digest_note(self, content: str) -> DigestResult:
        """消化单条笔记：生成标题、分类、标签"""
        pass
