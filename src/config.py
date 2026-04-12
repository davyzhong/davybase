# src/config.py
import json
import os
import yaml
from pathlib import Path
from typing import Optional


class Config:
    """配置管理"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config: dict = {}
        self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

    @property
    def vault_path(self) -> str:
        return self._config.get("vault_path", "/Users/qiming/ObsidianWiki")

    @property
    def data_path(self) -> str:
        return self._config.get("data_path", "./data")

    @property
    def default_provider(self) -> str:
        return self._config.get("compiler", {}).get("default_provider", "zhipu")

    @property
    def logs_path(self) -> str:
        return self._config.get("logs_path", "./logs")

    def get_getnote_credentials(self) -> tuple[str, str]:
        """获取 get 笔记 API 凭据"""
        api_key = os.environ.get("GETNOTE_API_KEY")
        client_id = os.environ.get("GETNOTE_CLIENT_ID")

        if not api_key:
            raise RuntimeError("未设置环境变量 GETNOTE_API_KEY，请运行 `/note config` 配置 get 笔记")
        if not client_id:
            raise RuntimeError("未设置环境变量 GETNOTE_CLIENT_ID，请运行 `/note config` 配置 get 笔记")

        return api_key, client_id

    def get_llm_api_key(self, provider: str) -> str:
        """获取 LLM API 密钥"""
        env_map = {"zhipu": "ZHIPU_API_KEY", "minimax": "MINIMAX_API_KEY"}
        env_var = env_map.get(provider)
        if not env_var:
            raise ValueError(f"未知提供商：{provider}")

        api_key = os.environ.get(env_var)
        if not api_key:
            raise RuntimeError(f"未设置环境变量 {env_var}")

        return api_key
