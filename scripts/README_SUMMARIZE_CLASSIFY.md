# 散落笔记批量处理脚本

## 功能说明

`summarize_and_classify.py` 脚本为 `_inbox` 目录中的散落笔记提供：
1. **标题生成** - 为无标题笔记自动生成简洁明确的标题
2. **智能分类** - 为笔记推荐知识库分类（现有匹配或新建建议）
3. **状态标识** - 在笔记 Frontmatter 中添加处理状态，避免重复处理

## 状态标识系统

脚本会在笔记的 Frontmatter 中添加以下标识字段：

```yaml
---
note_id: 1234567890
summarized: true              # 是否已生成标题
generated_title: "自动生成的标题"
summarized_at: '2026-04-13T06:15:20'
classified: true              # 是否已分类
recommended_kb: "经营&管理"    # 推荐的知识库
classification_action: "use_existing"  # 或 "create_new"
classification_confidence: "high"      # high/medium/low
classification_reason: "分类理由"
classified_at: '2026-04-13T06:16:32'
moved_to_kb: "经营&管理"       # 已移动到的知识库目录（--apply 执行后）
moved_at: '2026-04-13T06:21:34'
---
```

同时，处理状态会保存在 `data/.processing_status.json` 中，用于：
- 追踪已处理的笔记 ID
- 支持断点续传
- 避免重复处理

## 使用方法

### 1. 生成标题

```bash
# 预览模式（处理 2 条测试）
export MINIMAX_API_KEY="your_key_here"
python3 scripts/summarize_and_classify.py --summarize --limit 2

# 批量处理（每批 20 条）
python3 scripts/summarize_and_classify.py --summarize --batch-size 20

# 限制数量测试
python3 scripts/summarize_and_classify.py --summarize --limit 50
```

### 2. 分类笔记

```bash
# 预览模式
python3 scripts/summarize_and_classify.py --classify --limit 2

# 批量处理
python3 scripts/summarize_and_classify.py --classify --batch-size 20
```

### 3. 执行分类（创建知识库并移动笔记）

```bash
# 预览模式（先运行 --classify 生成分类标签）
python3 scripts/summarize_and_classify.py --classify --limit 10

# 执行分类（交互式确认新知识库）
python3 scripts/summarize_and_classify.py --apply

# 自动确认所有新知识库（无需逐个确认）
python3 scripts/summarize_and_classify.py --apply --auto-confirm

# 限制执行数量（测试用）
python3 scripts/summarize_and_classify.py --apply --limit 50
```

**执行流程**：
1. 先运行 `--classify` 为笔记生成分类标签
2. 再运行 `--apply` 创建知识库目录并移动笔记
3. 新知识库会提示确认（或使用 `--auto-confirm` 自动确认）

**注意事项**：
- 只有已分类的笔记（Frontmatter 中有 `classified: true`）才会被处理
- 新知识库目录会创建在 `raw/` 目录下
- 移动后的笔记状态会记录在 `.processing_status.json` 中

## 完整工作流程

```bash
# 步骤 1: 为无标题笔记生成标题
python3 scripts/summarize_and_classify.py --summarize --batch-size 50

# 步骤 2: 为笔记分类（生成分类标签）
python3 scripts/summarize_and_classify.py --classify --batch-size 50

# 步骤 3: 执行分类（创建知识库并移动笔记）
python3 scripts/summarize_and_classify.py --apply --auto-confirm

# 步骤 4: 查看处理结果
python3 -c "
import json
from pathlib import Path
status = json.load(open('raw/.processing_status.json'))
notes = status.get('notes', {})
print(f'已处理：{len(notes)} 条')
print(f'已生成标题：{len([n for n in notes.values() if n.get(\"summarized\")])} 条')
print(f'已分类：{len([n for n in notes.values() if n.get(\"classified\")])} 条')
print(f'已移动：{len([n for n in notes.values() if n.get(\"moved_to_kb\")])} 条')
"
```

## API 密钥配置

### 方式 1：环境变量（推荐）

```bash
export MINIMAX_API_KEY="sk-xxx..."
```

### 方式 2：secrets.yaml 文件

编辑 `secrets.yaml`：

```yaml
llm:
  minimax_api_key: "sk-xxx..."
```

## 处理进度查看

```bash
# 查看处理状态统计
python3 -c "
import json
from pathlib import Path
status_file = Path('/Users/qiming/ObsidianWiki/raw/.processing_status.json')
if status_file.exists():
    data = json.load(open(status_file))
    notes = data.get('notes', {})
    summarized = len([n for n in notes.values() if n.get('summarized')])
    classified = len([n for n in notes.values() if n.get('classified')])
    print(f'已记录笔记：{len(notes)}')
    print(f'已生成标题：{summarized}')
    print(f'已分类：{classified}')
'
```

## 注意事项

1. **API 限流**：脚本已内置限流控制（批次间隔 3 秒，请求间隔 1 秒）
2. **并发控制**：默认最多 3 个并发请求
3. **断点续传**：处理状态会自动保存，中断后运行会自动跳过已处理的笔记
4. **空内容笔记**：对于只有 ID 没有内容的笔记，生成的标题会是"记录 ID：xxx"格式

## 故障排除

### 401 Unauthorized

MiniMax API 密钥无效，检查：
- 密钥是否正确复制
- 密钥是否已过期

### API 限流 (429)

脚本会自动等待重试，也可以手动调整：
- 减小 `--batch-size`
- 增加批次间隔（修改脚本中的 `delay_between_batches`）
