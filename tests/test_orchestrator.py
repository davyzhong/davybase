"""
测试并发编排器
"""
import pytest
from pathlib import Path
from src.orchestrator import (
    IngestOrchestrator,
    DigestOrchestrator,
    CompileOrchestrator,
    compute_content_hash
)
from src.config import Config


class TestContentHash:
    """测试内容哈希计算"""

    def test_compute_hash(self):
        """测试哈希计算"""
        content = "test content"
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        assert hash1 == hash2  # 相同内容产生相同哈希

    def test_different_content(self):
        """测试不同内容"""
        hash1 = compute_content_hash("content1")
        hash2 = compute_content_hash("content2")
        assert hash1 != hash2

    def test_hash_length(self):
        """测试哈希长度"""
        hash_val = compute_content_hash("test")
        assert len(hash_val) == 16  # SHA256 前 16 字符


class TestIngestOrchestrator:
    """测试 IngestOrchestrator"""

    def test_init(self, tmp_path):
        """测试初始化"""
        config = Config()
        orchestrator = IngestOrchestrator(tmp_path, config)
        assert orchestrator.state is not None
        assert orchestrator.state_dir == tmp_path

    def test_select_provider_round_robin(self, tmp_path):
        """测试轮询选择（DigestOrchestrator）"""
        config = Config()
        orchestrator = DigestOrchestrator(tmp_path, config)

        # 轮询策略应该交替返回不同提供商
        provider1 = orchestrator._select_provider(0, "round_robin")
        provider2 = orchestrator._select_provider(1, "round_robin")
        assert provider1 != provider2

    def test_select_provider_single(self, tmp_path):
        """测试单一策略"""
        config = Config()
        orchestrator = DigestOrchestrator(tmp_path, config)

        # 单一策略应该始终返回同一提供商
        provider1 = orchestrator._select_provider(0, "single")
        provider2 = orchestrator._select_provider(5, "single")
        assert provider1 == provider2


class TestCompileOrchestrator:
    """测试 CompileOrchestrator"""

    def test_init(self, tmp_path):
        """测试初始化"""
        config = Config()
        orchestrator = CompileOrchestrator(tmp_path, config)
        assert orchestrator.state is not None

    def test_select_provider_round_robin(self, tmp_path):
        """测试轮询选择"""
        config = Config()
        orchestrator = CompileOrchestrator(tmp_path, config)

        # 轮询策略应该交替返回不同提供商
        provider1 = orchestrator._select_provider(0, "round_robin")
        provider2 = orchestrator._select_provider(1, "round_robin")
        assert provider1 != provider2


class TestPipelineIntegration:
    """测试管线集成"""

    def test_orchestrator_import(self):
        """测试编排器可以导入"""
        from src.orchestrator import IngestOrchestrator, DigestOrchestrator, CompileOrchestrator
        assert IngestOrchestrator is not None
        assert DigestOrchestrator is not None
        assert CompileOrchestrator is not None

    def test_main_cli_import(self):
        """测试 main.py CLI 可以导入"""
        from main import cli
        assert cli is not None
