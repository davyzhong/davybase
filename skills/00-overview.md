# Davybase 知识管理师

> 帮你把 get 笔记中的散落知识，转化为结构化、可检索、持续增厚的第二大脑。
>
> **风格**：有条理的知识策展人——安静、持续、有节奏地工作。

---

## 完整流水线

```
get 笔记 API → 采集 → 整理 → 创作 → Obsidian Wiki
              ↓      ↓      ↓
           01     02     03
```

| 阶段 | Skill | 职责 | 输出 |
|------|-------|------|------|
| **01** | [知识采集](01-collect.md) | 从 get 笔记 API 抓取原始内容 | `raw/notes/_inbox/*.md` |
| **02** | [知识整理](02-organize.md) | 消化 + 分类，归档到 16 个知识库 | `processed/{16 分类}/*.md` |
| **03** | [知识创作](03-create.md) | 编译 + 发布，生成结构化 Wiki 条目 | `wiki/{主题}.md` |

---

## 快速开始

### 每日自动
```
/01-collect   # 抓取 get 笔记新增内容
```

### 定期整理
```
/02-organize  # 消化 + 分类待处理笔记
```

### 按需创作
```
/03-create    # 编译 Wiki 条目并发布
```

---

## 配置要求

1. **get 笔记 API 凭据** — `secrets.yaml` 中的 `getnote.api_key` 和 `getnote.client_id`
2. **LLM API 密钥** — 智谱/MiniMax/千问，用于消化和编译
3. **Obsidian 路径** — `config.yaml` 中的 `vault_path`

---

## 状态查询

```
/status   # 查看完整管线状态
```

---

## 相关文件

- [01-collect.md](01-collect.md) — 知识采集
- [02-organize.md](02-organize.md) — 知识整理
- [03-create.md](03-create.md) — 知识创作
