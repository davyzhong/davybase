# src/config.py
import json
import os
import yaml
from pathlib import Path
from typing import Optional, Tuple


class Config:
    """配置管理"""

    def __init__(self, config_path: str = "config.yaml", secrets_path: str = "secrets.yaml"):
        self.config_path = Path(config_path)
        self.secrets_path = Path(secrets_path)
        self._config: dict = {}
        self._secrets: dict = {}
        self.load()

    def load(self):
        """加载配置文件和密钥文件"""
        # 加载主配置
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # 加载密钥配置
        if self.secrets_path.exists():
            with open(self.secrets_path, encoding="utf-8") as f:
                self._secrets = yaml.safe_load(f) or {}

    @property
    def vault_path(self) -> str:
        return self._config.get("vault_path", "/Users/qiming/ObsidianWiki")

    @property
    def data_path(self) -> str:
        return self._config.get("data_path", "./data")

    @property
    def logs_path(self) -> str:
        return self._config.get("logs_path", "./logs")

    @property
    def default_provider(self) -> str:
        return self._config.get("compiler", {}).get("default_provider", "zhipu")

    def get_getnote_credentials(self) -> Tuple[str, str]:
        """获取 get 笔记 API 凭据

        优先级：环境变量 > secrets.yaml > 错误
        """
        # 环境变量优先级最高
        api_key = os.environ.get("GETNOTE_API_KEY")
        client_id = os.environ.get("GETNOTE_CLIENT_ID")

        if api_key and client_id:
            return api_key, client_id

        # 从 secrets.yaml 读取
        api_key = self._secrets.get("getnote", {}).get("api_key")
        client_id = self._secrets.get("getnote", {}).get("client_id")

        if api_key and client_id:
            return api_key, client_id

        # 都没有则报错
        raise RuntimeError(
            "未配置 get 笔记 API 凭据。"
            "方式 1：运行 `/note config` 配置 get 笔记；"
            "方式 2：复制 secrets.example.yaml 为 secrets.yaml 并填入密钥"
        )

    def get_llm_api_key(self, provider: str) -> str:
        """获取 LLM API 密钥

        优先级：环境变量 > secrets.yaml > 错误
        """
        # 环境变量优先级最高
        env_map = {"zhipu": "ZHIPU_API_KEY", "minimax": "MINIMAX_API_KEY", "qwen": "QWEN_API_KEY"}
        env_var = env_map.get(provider)

        if env_var:
            api_key = os.environ.get(env_var)
            if api_key:
                return api_key

        # 从 secrets.yaml 读取
        llm_config = self._secrets.get("llm", {})
        key_map = {"zhipu": "zhipu_api_key", "minimax": "minimax_api_key", "qwen": "qwen_api_key"}
        secret_key = key_map.get(provider)

        if secret_key:
            api_key = llm_config.get(secret_key)
            if api_key:
                return api_key

        # 都没有则报错
        if provider == "zhipu":
            raise RuntimeError(
                f"未配置智谱 API 密钥。"
                f"方式 1：设置环境变量 ZHIPU_API_KEY；"
                f"方式 2：在 secrets.yaml 中配置 llm.zhipu_api_key"
            )
        elif provider == "minimax":
            raise RuntimeError(
                f"未配置 MiniMax API 密钥。"
                f"方式 1：设置环境变量 MINIMAX_API_KEY；"
                f"方式 2：在 secrets.yaml 中配置 llm.minimax_api_key"
            )
        elif provider == "qwen":
            raise RuntimeError(
                f"未配置千问 API 密钥。"
                f"方式 1：设置环境变量 QWEN_API_KEY；"
                f"方式 2：在 secrets.yaml 中配置 llm.qwen_api_key"
            )
        else:
            raise ValueError(f"未知 LLM 提供商：{provider}")

    def get_batch_size(self) -> int:
        """获取批处理大小"""
        return self._config.get("compiler", {}).get("batch_size", 15)

    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        return self._config.get("compiler", {}).get("max_retries", 2)

    def get_rate_limit_delay(self) -> float:
        """获取 API 请求间隔（秒）"""
        return self._config.get("sync", {}).get("rate_limit_delay", 1.0)
