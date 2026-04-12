# Davybase 使用指南

详细的 Davybase 使用说明和常见工作流。

## 快速开始

### 1. 配置环境

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入你的 API 密钥
# - get 笔记 API 凭据：运行 /note config 获取
# - LLM API 密钥：从智谱 AI 或 MiniMax 平台获取
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 验证配置

```bash
# 检查配置是否加载成功
python main.py status

# 测试 LLM 配额
python main.py quota
```

### 4. 运行全量同步

```bash
# 使用智谱 GLM5 进行全量同步
python main.py full-sync --provider zhipu

# 或使用 MiniMax M2.7
python main.py full-sync --provider minimax
```

---

## 常见工作流

### 全量同步 (Full Sync)

首次使用或需要完全重建 Wiki 时使用：

```bash
python main.py full-sync --provider zhipu
```

**过程说明：**
1. Extractor 从 get 笔记 API 获取所有笔记
2. Converter 格式化笔记为标准 Markdown
3. Compiler 调用 LLM 编译笔记为 Wiki 条目
4. Writer 写入 Obsidian Vault

**预计耗时：** 取决于笔记数量，约 10-30 分钟

### 增量同步 (Incremental Sync)

日常使用，仅同步新增或修改的笔记：

```bash
python main.py incremental
```

**特点：**
- 自动检测新增/修改的笔记
- 跳过未变化的笔记
- 支持断点续传

**从中断处恢复：**
```bash
python main.py incremental --resume
```

### 仅编译模式

如果已有原始笔记，仅需 LLM 编译：

```bash
python main.py compile-only --provider zhipu
```

### 预览模式

测试配置，不实际写入文件：

```bash
python main.py full-sync --dry-run
```

---

## 命令行参数

### 全局参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--provider <name>` | LLM 提供商 (zhipu/minimax) | config.yaml 中的 default_provider |
| `--batch-size <N>` | 单批次处理笔记数 | 15 |
| `--resume` | 从中断处恢复 | false |
| `--dry-run` | 预览模式，不实际写入 | false |
| `--verbose` | 详细日志输出 | false |

### 命令示例

```bash
# 使用 MiniMax，批处理大小 50
python main.py full-sync --provider minimax --batch-size 50

# 增量同步，详细日志
python main.py incremental --verbose

# 预览模式
python main.py compile-only --dry-run

# 从中断处恢复
python main.py incremental --resume
```

---

## 故障排查

### 常见问题

#### 1. API Key 未设置

```
错误：GETNOTE_API_KEY not set
```

**解决：**
```bash
# 运行 getnote Skill 配置
/note config

# 或手动设置环境变量
export GETNOTE_API_KEY=gk_live_xxx
export GETNOTE_CLIENT_ID=cli_xxx
```

#### 2. LLM 配额不足

```
错误：API quota exceeded
```

**解决：**
- 检查 LLM 平台配额余额
- 切换到备用提供商：`--provider minimax`
- 充值 API 配额

#### 3. Obsidian Vault 路径不存在

```
错误：vault_path does not exist
```

**解决：**
- 检查 `config.yaml` 中的 `vault_path` 配置
- 确保 Obsidian 已打开该 Vault

#### 4. 同步中断后恢复

```bash
# 使用 --resume 参数继续
python main.py incremental --resume
```

### 日志位置

日志文件位于 `logs/` 目录（需在 `config.yaml` 中配置）：

```bash
# 查看最新日志
tail -f logs/davybase.log

# 查看错误日志
grep ERROR logs/davybase.log
```

---

## 最佳实践

### 1. 首次同步

建议先运行小批量测试配置：

```bash
# 先处理 5 条笔记测试
python main.py full-sync --batch-size 5 --dry-run

# 确认无误后全量运行
python main.py full-sync --provider zhipu
```

### 2. 日常同步

设置定时任务（如 cron）：

```bash
# 每天早上 6 点自动同步
0 6 * * * cd /path/to/davybase && python main.py incremental
```

### 3. 批处理大小调整

根据 API 限流情况调整：

- 默认 `batch_size: 15`
- 如果频繁触发限流，降低到 `5-10`
- 如果配额充足，可提高到 `30-50`

### 4. 多提供商降级

配置自动降级策略：

```yaml
compiler:
  default_provider: zhipu
  # 如果 zhipu 失败，自动切换到 minimax
```

---

## FAQ

### Q: 全量同步和增量同步有什么区别？

**A:** 
- **全量同步**：处理所有笔记，适合首次使用或完全重建
- **增量同步**：仅处理新增/修改的笔记，适合日常使用

### Q: 如何知道同步是否完成？

**A:** 
- 查看命令行输出的统计信息
- 检查 `wiki/` 目录的文件数量
- 运行 `python main.py status` 查看同步状态

### Q: 同步过程中可以中断吗？

**A:** 
可以。使用 `--resume` 参数从中断处继续：
```bash
python main.py incremental --resume
```

### Q: 如何清空同步状态重新同步？

**A:** 
删除 SQLite 数据库文件：
```bash
rm data/sync.db
python main.py full-sync
```

### Q: 支持哪些 LLM 提供商？

**A:** 
目前支持：
- **智谱 GLM5** (`zhipu`) - 默认，通用场景
- **MiniMax M2.7** (`minimax`) - 中文理解更好，降级选择

---

## 相关文档

- [README.md](../README.md) - 项目概述和快速开始
- [CONFIGURATION.md](CONFIGURATION.md) - 配置指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 系统架构说明
