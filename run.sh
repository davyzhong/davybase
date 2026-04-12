#!/usr/bin/env bash
# 从 ~/.openclaw/openclaw.json 读取 GetNote 配置并运行 Davybase
# 从 ~/.zshrc 读取 LLM API 密钥

# 读取 GetNote API Key
API_KEY=$(python3 -c "import json; print(json.load(open('$HOME/.openclaw/openclaw.json'))['skills']['entries']['getnote']['apiKey'])")
CLIENT_ID="cli_a1b2c3d4e5f6789012345678abcdef90"

# 从 .zshrc 读取 LLM API 密钥
MINIMAX_KEY=$(grep 'MINIMAX_KEY=' ~/.zshrc | cut -d'"' -f2)
ZHIPU_KEY=$(grep 'ZHIPU_API_KEY=' ~/.zshrc | cut -d'"' -f2)

export GETNOTE_API_KEY="$API_KEY"
export GETNOTE_CLIENT_ID="$CLIENT_ID"
export MINIMAX_API_KEY="$MINIMAX_KEY"
export ZHIPU_API_KEY="$ZHIPU_KEY"

cd /Users/qiming/workspace/davybase
python3 main.py "$@"
