# Davybase 定时任务配置指南

## Claude Cron 配置

### 方式 1: 使用 CronCreate API

编辑 `~/.claude/scheduled_tasks.json`（如不存在则创建）：

```json
{
  "jobs": [
    {
      "id": "davybase-daily-ingest",
      "name": "Davybase 每日摄取",
      "cron": "0 3 * * *",
      "prompt": "摄取最近 100 条笔记，batch_size=100，resume=true",
      "durable": true,
      "recurring": true
    },
    {
      "id": "davybase-daily-digest",
      "name": "Davybase 每日消化",
      "cron": "0 4 * * *",
      "prompt": "消化 inbox 中所有待处理笔记，apply=true，provider=minimax",
      "durable": true,
      "recurring": true
    },
    {
      "id": "davybase-daily-compile",
      "name": "Davybase 每日编译",
      "cron": "0 5 * * *",
      "prompt": "编译所有达到阈值（≥3 条）的知识库",
      "durable": true,
      "recurring": true
    },
    {
      "id": "davybase-daily-report",
      "name": "Davybase 每日报告",
      "cron": "0 7 * * *",
      "prompt": "生成今天的执行报告",
      "durable": true,
      "recurring": true
    }
  ]
}
```

### 方式 2: 使用传统 crontab

```bash
crontab -e
```

添加以下内容：

```bash
# Davybase 知识生产线定时任务
# 每天凌晨 3 点摄取
0 3 * * * cd /Users/qiming/workspace/davybase && python src/mcp_server.py <<EOF
ingest_notes(batch_size=100, resume=true)
EOF

# 每天凌晨 4 点消化
0 4 * * * cd /Users/qiming/workspace/davybase && python src/mcp_server.py <<EOF
digest_notes(apply=true, provider=minimax)
EOF

# 每天凌晨 5 点编译
0 5 * * * cd /Users/qiming/workspace/davybase && python src/mcp_server.py <<EOF
compile_notes(threshold=3, provider=zhipu)
EOF
```

### 方式 3: 使用 shell 脚本

创建 `scripts/daily_pipeline.sh`：

```bash
#!/bin/bash
# Davybase 每日知识生产线执行脚本

set -e

DATE=$(date +%Y%m%d)
LOG_DIR="/Users/qiming/ObsidianWiki/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/daily_$DATE.log"
}

cd /Users/qiming/workspace/davybase

log "========== 开始每日知识生产线 =========="

# 阶段 1: 摄取
log "[1/4] 摄取阶段..."
python -c "
import asyncio
from src.mcp_server import ingest_notes
result = asyncio.run(ingest_notes(batch_size=100, resume=True))
print(result)
" || log "摄取阶段失败"

# 阶段 2: 消化
log "[2/4] 消化阶段..."
python -c "
import asyncio
from src.mcp_server import digest_notes
result = asyncio.run(digest_notes(apply=True, provider='minimax'))
print(result)
" || log "消化阶段失败"

# 阶段 3: 编译
log "[3/4] 编译阶段..."
python -c "
import asyncio
from src.mcp_server import compile_notes
result = asyncio.run(compile_notes(kb_dir='processed/编程+AI/', threshold=3, provider='zhipu'))
print(result)
" || log "编译阶段失败"

# 阶段 4: 发布
log "[4/4] 发布阶段..."
python -c "
import asyncio
from src.mcp_server import get_pipeline_status
result = asyncio.run(get_pipeline_status())
print(result)
"

log "========== 每日知识生产线完成 =========="
```

配置 crontab：

```bash
0 3 * * * /Users/qiming/workspace/davybase/scripts/daily_pipeline.sh >> /Users/qiming/ObsidianWiki/logs/cron.log 2>&1
```

---

## 手动触发

### 使用 MCP Tools

```python
# Python 方式
import asyncio
from src.mcp_server import ingest_notes, digest_notes, compile_notes, get_pipeline_status

async def run_pipeline():
    # 摄取
    ingest_result = await ingest_notes(batch_size=100, resume=True)
    print(f"摄取：{ingest_result}")
    
    # 消化
    digest_result = await digest_notes(apply=True)
    print(f"消化：{digest_result}")
    
    # 编译
    compile_result = await compile_notes(kb_dir="processed/编程+AI/", threshold=3)
    print(f"编译：{compile_result}")
    
    # 状态
    status = await get_pipeline_status()
    print(f"状态：{status}")

asyncio.run(run_pipeline())
```

### 使用 Claude 自然语言

直接与 Claude 对话：

```
/ingest 摄取最近 100 条笔记
/digest 消化 inbox 中的笔记
/compile 编译编程+AI 知识库
/status 查看管线状态
```

---

## 通知配置

### 邮件通知

编辑 `scripts/notify.py`：

```python
#!/usr/bin/env python3
"""发送执行报告邮件"""
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def send_report(subject: str, body: str):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'davybase@example.com'
    msg['To'] = 'user@example.com'
    
    with smtplib.SMTP('smtp.example.com', 587) as server:
        server.starttls()
        server.login('user', 'password')
        server.send_message(msg)

# 使用
send_report(
    f"Davybase 执行报告 - {datetime.now().strftime('%Y-%m-%d')}",
    "执行内容..."
)
```

### 企业微信通知

```python
import requests

def send_wechat(content: str):
    webhook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX"
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    requests.post(webhook, json=data)
```

---

## 故障排查

### 任务未执行

检查 Cron 日志：
```bash
tail -f /var/log/cron.log
```

检查 Claude Cron 状态：
```bash
cat ~/.claude/scheduled_tasks.json
```

### MCP 服务未响应

测试 MCP 服务：
```bash
python -c "from src.mcp_server import mcp; print('OK')"
```

### 状态数据异常

检查状态文件：
```bash
ls -la /Users/qiming/ObsidianWiki/.davybase/progress/
cat /Users/qiming/ObsidianWiki/.davybase/progress/*.json
```

---

## 最佳实践

1. **执行时间**：避免在业务高峰期执行，建议凌晨 3-5 点
2. **批次大小**：根据 API 配额调整，建议 50-100
3. **断点续传**：始终启用 `resume=true`
4. **错误处理**：每个阶段独立，失败不影响后续
5. **日志记录**：保留至少 7 天日志便于排查
