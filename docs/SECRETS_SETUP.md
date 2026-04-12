# Davybase 密钥配置指南

本文档说明如何配置 Davybase 所需的 API 密钥。

## 配置方式

Davybase 支持两种密钥配置方式，**优先级如下**：

1. **环境变量**（优先级高，适合临时/CI 环境）
2. **secrets.yaml 文件**（推荐，适合本地开发）

---

## 方式一：secrets.yaml 文件（推荐）

### 步骤

1. **复制示例文件**

```bash
cp secrets.example.yaml secrets.yaml
```

2. **编辑 secrets.yaml**

```yaml
# get 笔记 API 凭据
getnote:
  api_key: "gk_live_xxx"          # 替换为你的 API Key
  client_id: "cli_xxx"             # 替换为你的 Client ID

# LLM API 密钥
llm:
  zhipu_api_key: "your_zhipu_api_key"
  minimax_api_key: "your_minimax_api_key"
```

3. **设置文件权限**（重要！）

```bash
chmod 600 secrets.yaml
```

### 获取 API 密钥

| 密钥 | 获取方式 |
|------|----------|
| `GETNOTE_API_KEY` | 运行 `/note config` 或在 [get 笔记开放平台](https://openapi.biji.com) 申请 |
| `GETNOTE_CLIENT_ID` | 运行 `/note config` 获取 |
| `ZHIPU_API_KEY` | [智谱 AI 开放平台](https://open.bigmodel.cn/) |
| `MINIMAX_API_KEY` | [MiniMax 开放平台](https://platform.minimaxi.com/) |

---

## 方式二：环境变量

适合临时使用或 CI/CD 环境。

### Bash/Zsh

```bash
# get 笔记
export GETNOTE_API_KEY=gk_live_xxx
export GETNOTE_CLIENT_ID=cli_xxx

# 智谱
export ZHIPU_API_KEY=your_zhipu_api_key

# MiniMax
export MINIMAX_API_KEY=your_minimax_api_key
```

### 添加到 ~/.zshrc（永久生效）

```bash
echo 'export GETNOTE_API_KEY=gk_live_xxx' >> ~/.zshrc
echo 'export GETNOTE_CLIENT_ID=cli_xxx' >> ~/.zshrc
echo 'export ZHIPU_API_KEY=your_zhipu_api_key' >> ~/.zshrc
echo 'export MINIMAX_API_KEY=your_minimax_api_key' >> ~/.zshrc
source ~/.zshrc
```

---

## 验证配置

```bash
# 检查配置是否加载成功
python main.py status

# 测试 get 笔记 API 配额
python main.py quota
```

---

## 安全说明

### secrets.yaml 文件

- ✅ 已添加到 `.gitignore`，不会被提交到 Git
- ✅ 设置权限 `chmod 600`，仅所有者可读
- ✅ 集中管理所有密钥，便于维护

### 环境变量

- ✅ 适合 CI/CD 环境
- ✅ 适合多用户共享服务器
- ⚠️ 注意不要在日志中泄露

---

## 故障排查

### 问题 1：提示 "未配置 API 密钥"

**检查配置是否存在：**

```bash
# 检查 secrets.yaml 是否存在
ls -la secrets.yaml

# 检查环境变量是否设置
env | grep -E 'GETNOTE|ZHIPU|MINIMAX'
```

### 问题 2：配置文件格式错误

**验证 YAML 格式：**

```bash
python -c "import yaml; yaml.safe_load(open('secrets.yaml'))"
```

### 问题 3：密钥不生效

**优先级检查：** 环境变量会覆盖 secrets.yaml。如果同时配置了两者，环境变量优先级更高。

---

## 相关文件

- `secrets.example.yaml` - 配置模板
- `secrets.yaml` - 实际使用的配置文件（需手动创建，已排除在 Git 之外）
- [CONFIGURATION.md](CONFIGURATION.md) - 完整配置指南
