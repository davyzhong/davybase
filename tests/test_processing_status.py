"""
测试 processing_status 模块
"""
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.processing_status import (
    IngestStatus,
    DigestStatus,
    CompileStatus,
    PublishStatus,
    PipelineStatus,
    IngestRecord,
    DigestRecord,
    CompileRecord,
    PublishRecord,
    LegacyProcessingStatus,
)


@pytest.fixture
def temp_state_dir():
    """创建临时状态目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestIngestStatus:
    """测试 IngestStatus"""

    def test_init_empty(self, temp_state_dir):
        """测试初始化空状态"""
        status = IngestStatus(temp_state_dir)
        assert "notes" in status._data
        assert "last_updated" in status._data

    def test_mark_processed(self, temp_state_dir):
        """测试标记已摄取"""
        status = IngestStatus(temp_state_dir)
        record = IngestRecord(
            note_id="123456",
            source="getnote",
            raw_path="raw/notes/_inbox/123456.md",
            ingested_at=datetime.now().isoformat()
        )
        status.mark_processed("123456", record)

        assert status.is_processed("123456")
        rec = status.get_record("123456")
        assert rec is not None
        assert rec["note_id"] == "123456"

    def test_is_extracted_compatibility(self, temp_state_dir):
        """测试兼容旧格式的 is_extracted"""
        status = IngestStatus(temp_state_dir)
        # 旧格式使用 extracted_ids 列表
        status._data["extracted_ids"] = ["111", "222"]
        status._save()

        assert status.is_extracted("111")
        assert status.is_extracted("222")
        assert not status.is_extracted("333")

    def test_get_extracted_ids(self, temp_state_dir):
        """测试获取已抽取 ID 集合"""
        status = IngestStatus(temp_state_dir)
        status._data["extracted_ids"] = ["111", "222"]
        status._data["notes"] = {"333": {"note_id": "333"}}
        status._save()

        ids = status.get_extracted_ids()
        assert ids == {"111", "222", "333"}

    def test_snapshot(self, temp_state_dir):
        """测试状态快照"""
        status = IngestStatus(temp_state_dir)
        status._data["extracted_ids"] = ["1"] * 100
        status._save()

        snapshot = status.snapshot()
        assert snapshot["total_extracted"] == 100
        assert snapshot["status"] == "completed"

    def test_snapshot_empty(self, temp_state_dir):
        """测试空状态快照"""
        status = IngestStatus(temp_state_dir)
        snapshot = status.snapshot()
        assert snapshot["total_extracted"] == 0
        assert snapshot["status"] == "pending"


class TestDigestStatus:
    """测试 DigestStatus"""

    def test_is_processed(self, temp_state_dir):
        """测试 is_processed 检查"""
        status = DigestStatus(temp_state_dir)
        status._data["notes"] = {
            "123": {"summarized": True, "classified": True},
            "456": {"summarized": True, "classified": False},
            "789": {"summarized": False, "classified": False},
        }
        status._save()

        assert status.is_processed("123")
        assert not status.is_processed("456")
        assert not status.is_processed("789")

    def test_mark_summarized(self, temp_state_dir):
        """测试标记已生成标题"""
        status = DigestStatus(temp_state_dir)
        status.mark_summarized("123", "测试标题")

        note = status.get_record("123")
        assert note is not None
        assert note["summarized"] is True
        assert note["generated_title"] == "测试标题"

    def test_mark_classified(self, temp_state_dir):
        """测试标记已分类"""
        status = DigestStatus(temp_state_dir)
        status.mark_classified(
            "123",
            kb="编程+AI",
            action="use_existing",
            confidence="high"
        )

        note = status.get_record("123")
        assert note is not None
        assert note["classified"] is True
        assert note["recommended_kb"] == "编程+AI"
        assert note["action"] == "use_existing"

    def test_mark_moved(self, temp_state_dir):
        """测试标记已移动"""
        status = DigestStatus(temp_state_dir)
        status.mark_moved("123", "编程+AI")

        note = status.get_record("123")
        assert note is not None
        assert note["moved_to_kb"] == "编程+AI"

    def test_get_pending_count(self, temp_state_dir):
        """测试获取待处理数量"""
        status = DigestStatus(temp_state_dir)
        status._data["notes"] = {
            "123": {"summarized": True, "classified": True},
            "456": {"summarized": True, "classified": False},
        }
        status._save()

        assert status.get_pending_count() == 1


class TestCompileStatus:
    """测试 CompileStatus"""

    def test_mark_processed(self, temp_state_dir):
        """测试标记已编译"""
        status = CompileStatus(temp_state_dir)
        record = CompileRecord(
            wiki_title="反向传播算法",
            source_notes=["note1", "note2"],
            wiki_path="wiki/反向传播算法.md",
            provider="zhipu"
        )
        status.mark_processed("反向传播算法", record)

        assert status.is_processed("反向传播算法")
        assert status.get_compiled_count() == 1


class TestPublishStatus:
    """测试 PublishStatus"""

    def test_mark_processed(self, temp_state_dir):
        """测试标记已发布"""
        status = PublishStatus(temp_state_dir)
        record = PublishRecord(
            wiki_title="反向传播算法",
            card_path="cards/2026-04-13/card_001.html"
        )
        status.mark_processed("反向传播算法", record)

        assert status.is_processed("反向传播算法")


class TestPipelineStatus:
    """测试 PipelineStatus"""

    def test_snapshot(self, temp_state_dir):
        """测试完整管线快照"""
        pipeline = PipelineStatus(temp_state_dir)
        snapshot = pipeline.snapshot()

        assert "ingest" in snapshot
        assert "digest" in snapshot
        assert "compile" in snapshot
        assert "publish" in snapshot
        assert "generated_at" in snapshot

    def test_format_progress(self, temp_state_dir):
        """测试进度格式化输出"""
        pipeline = PipelineStatus(temp_state_dir)
        # 添加一些测试数据
        pipeline.ingest._data["extracted_ids"] = ["1"] * 10
        pipeline.digest._data["notes"] = {"1": {"summarized": True, "moved_to_kb": "KB1"}}
        pipeline.compile._data["wiki_entries"] = {"wiki1": {}}
        pipeline.publish._data["cards"] = {"card1": {}}

        output = pipeline.format_progress()
        assert "摄取阶段：10 条笔记" in output
        assert "消化阶段：1 条已处理" in output
        assert "编译阶段：1 个 Wiki 条目" in output


class TestLegacyProcessingStatus:
    """测试 LegacyProcessingStatus 兼容性"""

    def test_is_summarized(self, temp_state_dir):
        """测试已生成标题检查"""
        # 模拟旧格式状态文件
        status_file = temp_state_dir / ".processing_status.json"
        status_file.write_text(json.dumps({
            "notes": {
                "123": {"summarized": True, "generated_title": "标题"}
            }
        }, ensure_ascii=False), encoding='utf-8')

        status = LegacyProcessingStatus(temp_state_dir)
        assert status.is_summarized("123")
        assert not status.is_summarized("456")

    def test_mark_operations(self, temp_state_dir):
        """测试标记操作"""
        # 创建状态文件以初始化
        status_file = temp_state_dir / ".processing_status.json"
        status_file.write_text(json.dumps({"notes": {}}, ensure_ascii=False), encoding='utf-8')

        status = LegacyProcessingStatus(temp_state_dir)

        status.mark_summarized("123", {"summarized": True, "generated_title": "标题"})
        assert status.is_summarized("123")

        status.mark_classified("123", {"classified": True, "recommended_kb": "编程+AI"})
        assert status.is_classified("123")

        status.mark_moved("123", {"moved_to_kb": "编程+AI"})
        assert status.is_moved("123")


def mock_datetime():
    """模拟时间戳用于测试比较"""
    return datetime.now().isoformat()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
