# tests/test_cli.py
from click.testing import CliRunner
from main import cli


def test_status_command(tmp_path, monkeypatch):
    """测试 status 命令"""
    # 设置测试数据目录
    test_data = tmp_path / "data"
    test_data.mkdir()
    monkeypatch.setattr("src.config.Config.__init__", lambda self, config_path="config.yaml": setattr(self, "config_path", test_data.parent / "config.yaml") or setattr(self, "_config", {"data_path": str(test_data), "vault_path": str(tmp_path / "vault"), "logs_path": str(tmp_path / "logs")}) or None)

    # 创建测试数据库
    db_path = test_data / "sync.db"
    from src.sync_state import SyncState
    state = SyncState(str(db_path))
    state.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["status"], catch_exceptions=False)
    assert result.exit_code == 0


def test_cli_help():
    """测试 CLI 帮助信息"""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Davybase" in result.output
    # Click 将下划线转换为连字符
    assert "full-sync" in result.output
    assert "incremental" in result.output
    assert "extract-only" in result.output
    assert "compile-only" in result.output
    assert "status" in result.output
    assert "quota" in result.output


def test_full_sync_help():
    """测试 full-sync 命令帮助"""
    runner = CliRunner()
    result = runner.invoke(cli, ["full-sync", "--help"])
    assert result.exit_code == 0
    assert "--provider" in result.output


def test_incremental_help():
    """测试 incremental 命令帮助"""
    runner = CliRunner()
    result = runner.invoke(cli, ["incremental", "--help"])
    assert result.exit_code == 0
    assert "--provider" in result.output


def test_compile_only_help():
    """测试 compile-only 命令帮助"""
    runner = CliRunner()
    result = runner.invoke(cli, ["compile-only", "--help"])
    assert result.exit_code == 0
    assert "--provider" in result.output


def test_extract_only_help():
    """测试 extract-only 命令帮助"""
    runner = CliRunner()
    result = runner.invoke(cli, ["extract-only", "--help"])
    assert result.exit_code == 0


def test_quota_help():
    """测试 quota 命令帮助"""
    runner = CliRunner()
    result = runner.invoke(cli, ["quota", "--help"])
    assert result.exit_code == 0
