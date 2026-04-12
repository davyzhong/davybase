#!/usr/bin/env python3
"""
散落笔记批量处理脚本
- 为无标题笔记生成标题
- 为笔记推荐知识库分类
- 添加处理状态标识，避免重复处理
"""
import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx
import yaml

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.sync_state import SyncState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("davybase.summarize_classify")

# API 配置
GETNOTE_BASE_URL = "https://openapi.biji.com"
MINIMAX_URL = "https://api.minimaxi.com/v1/chat/completions"
MINIMAX_MODEL = "codex-MiniMax-M2.7"

# Prompt 模板
TITLE_GENERATION_PROMPT = """请为以下笔记内容生成一个简洁明确的标题（10-30 字）：

笔记内容：
{content}

要求：
1. 标题应准确概括笔记核心内容
2. 避免使用"关于"、"简介"等泛化词汇
3. 如果是技术内容，包含关键技术术语
4. 如果是业务内容，包含关键业务概念
5. 只输出标题，不要有其他内容、解释或思考过程

标题："""

CLASSIFICATION_PROMPT = """请分析以下笔记内容，完成分类任务：

**现有知识库列表**：{kb_list}

**笔记内容**：
{content}

**分类规则**：
1. 如果内容与现有知识库高度匹配，推荐现有知识库，action 为 "use_existing"
2. 如果内容无法匹配现有知识库，建议一个新的知识库名称，action 为 "create_new"
3. 置信度：high（明确匹配）/ medium（可能匹配）/ low（不确定）

请按 JSON 格式输出（只输出 JSON，不要有其他内容）：
{{
    "recommended_kb": "知识库名称",
    "action": "use_existing" 或 "create_new",
    "confidence": "high/medium/low",
    "reason": "分类理由"
}}"""


class ProcessingStatus:
    """处理状态标识管理器"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.status_file = data_dir / ".processing_status.json"
        self.status: Dict[str, Dict] = self._load_status()

    def _load_status(self) -> Dict:
        """加载处理状态"""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载状态文件失败：{e}")
        return {"notes": {}}

    def save(self):
        """保存处理状态"""
        self.status["last_updated"] = datetime.now().isoformat()
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)

    def get_note_status(self, note_id: str) -> Dict:
        """获取单个笔记的处理状态"""
        return self.status["notes"].get(note_id, {})

    def set_note_status(self, note_id: str, status_updates: Dict):
        """更新笔记处理状态"""
        if note_id not in self.status["notes"]:
            self.status["notes"][note_id] = {"note_id": note_id}

        self.status["notes"][note_id].update(status_updates)
        self.status["notes"][note_id]["updated_at"] = datetime.now().isoformat()
        self.save()

    def is_summarized(self, note_id: str) -> bool:
        """检查是否已生成标题"""
        return self.status["notes"].get(note_id, {}).get("summarized", False)

    def is_classified(self, note_id: str) -> bool:
        """检查是否已分类"""
        return self.status["notes"].get(note_id, {}).get("classified", False)

    def get_unsummarized_notes(self, inbox_dir: Path) -> List[Path]:
        """获取未生成标题的笔记文件列表"""
        unsummarized = []
        for md_file in inbox_dir.glob("*.md"):
            note_id = self._extract_note_id(md_file)
            if note_id and not self.is_summarized(note_id):
                # 检查文件是否已经有真实标题
                if not self._has_real_title(md_file):
                    unsummarized.append(md_file)
        return unsummarized

    def get_unclassified_notes(self, inbox_dir: Path) -> List[Path]:
        """获取未分类的笔记文件列表"""
        unclassified = []
        for md_file in inbox_dir.glob("*.md"):
            note_id = self._extract_note_id(md_file)
            if note_id and not self.is_classified(note_id):
                unclassified.append(md_file)
        return unclassified

    def _extract_note_id(self, file_path: Path) -> Optional[str]:
        """从文件或内容中提取 note_id"""
        # 尝试从文件名提取
        parts = file_path.stem.split('_', 1)
        if parts and parts[0].isdigit():
            return parts[0]

        # 尝试从内容提取
        try:
            content = file_path.read_text(encoding='utf-8')
            for line in content.split('\n'):
                if line.startswith('note_id:'):
                    return line.split(':', 1)[1].strip()
        except Exception:
            pass
        return None

    def _has_real_title(self, file_path: Path) -> bool:
        """检查笔记是否有真实标题（不是 note_id）"""
        try:
            content = file_path.read_text(encoding='utf-8')
            for line in content.split('\n'):
                if line.startswith('title:'):
                    title = line.split(':', 1)[1].strip()
                    # 如果 title 是纯数字或等于文件名前缀，说明不是真实标题
                    if title.isdigit():
                        return False
                    note_id = self._extract_note_id(file_path)
                    if title == note_id:
                        return False
                    return True
        except Exception:
            pass
        return False


class NoteProcessor:
    """笔记处理器 - 生成标题和分类"""

    def __init__(self, config: Config):
        self.config = config
        self.data_dir = Path(config.data_path)
        self.inbox_dir = self.data_dir / "_inbox"
        self.status = ProcessingStatus(self.data_dir)
        self.semaphore = asyncio.Semaphore(3)  # 并发控制

        # 缓存知识库列表
        self._kb_cache: Optional[List[dict]] = None

    async def generate_title(self, content: str, api_key: str) -> str:
        """调用 MiniMax 生成标题"""
        prompt = TITLE_GENERATION_PROMPT.format(content=content[:3000])

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0)) as client:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.post(
                        MINIMAX_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": MINIMAX_MODEL,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )

                    if response.status_code == 429:
                        retry_after = min(60, 10 * (2 ** attempt))
                        logger.warning(f"API 限流，等待 {retry_after} 秒...")
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    title = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                    # 清理 markdown 格式和 <think> 标签
                    if title.startswith("```"):
                        title = title.split("```")[1].strip() if "```" in title[3:] else title[3:].strip()
                    if title.startswith('"') and title.endswith('"'):
                        title = title[1:-1]

                    # 清理 <think> 标签（MiniMax 可能返回思考过程）
                    if "<think>" in title:
                        # 提取 <think> 之后的内容
                        parts = title.split("</think>", 1)
                        if len(parts) > 1:
                            title = parts[1].strip()
                        else:
                            # 如果没有 </think>，取 <think> 之前的内容或最后一行
                            last_line = title.split('\n')[-1].strip()
                            title = last_line if last_line else "无标题"

                    # 清理可能的前导/后随标点
                    title = title.strip('.:,;:;:!:?!"\'""""')

                    return title if title else "无标题"

                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = min(60, 10 * (2 ** attempt))
                        logger.warning(f"API 错误，等待 {wait_time} 秒后重试：{e}")
                        await asyncio.sleep(wait_time)
                    else:
                        raise RuntimeError(f"MiniMax API 调用失败：{e}")

        raise RuntimeError("MiniMax API 调用失败：超过最大重试次数")

    async def classify_note(
        self,
        content: str,
        existing_kbs: List[dict],
        api_key: str
    ) -> dict:
        """调用 MiniMax 分类笔记"""
        kb_names = ", ".join([kb["name"] for kb in existing_kbs[:10]])
        if not kb_names:
            kb_names = "无现有知识库"

        prompt = CLASSIFICATION_PROMPT.format(
            kb_list=kb_names,
            content=content[:3000]
        )

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0)) as client:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.post(
                        MINIMAX_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": MINIMAX_MODEL,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )

                    if response.status_code == 429:
                        retry_after = min(60, 10 * (2 ** attempt))
                        logger.warning(f"API 限流，等待 {retry_after} 秒...")
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    llm_output = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                    # 解析 JSON
                    # 清理可能的 markdown 格式
                    if "```json" in llm_output:
                        llm_output = llm_output.split("```json")[1].split("```")[0].strip()
                    elif "```" in llm_output:
                        llm_output = llm_output.split("```")[1].split("```")[0].strip()

                    try:
                        result = json.loads(llm_output)
                        return result
                    except json.JSONDecodeError:
                        # 尝试用正则提取 JSON
                        match = re.search(r'\{[^}]+\}', llm_output)
                        if match:
                            return json.loads(match.group())
                        raise ValueError(f"无法解析 LLM 输出：{llm_output[:200]}")

                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = min(60, 10 * (2 ** attempt))
                        logger.warning(f"API 错误，等待 {wait_time} 秒后重试：{e}")
                        await asyncio.sleep(wait_time)
                    else:
                        raise RuntimeError(f"MiniMax API 调用失败：{e}")

        raise RuntimeError("MiniMax API 调用失败：超过最大重试次数")

    async def get_knowledge_bases(self) -> List[dict]:
        """获取知识库列表（带缓存）"""
        if self._kb_cache is not None:
            return self._kb_cache

        credentials = self.config.get_getnote_credentials()
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_kbs = []
            next_cursor = 0

            while True:
                try:
                    response = await client.get(
                        f"{GETNOTE_BASE_URL}/open/api/v1/resource/knowledge/list",
                        params={"cursor": next_cursor} if next_cursor else {},
                        headers={
                            "Authorization": credentials[0],
                            "X-Client-ID": credentials[1]
                        }
                    )

                    if response.status_code == 429:
                        await asyncio.sleep(60)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    kbs = data.get("data", {}).get("knowledges", [])
                    all_kbs.extend(kbs)

                    has_more = data.get("data", {}).get("has_more", False)
                    if not has_more:
                        break

                    next_cursor = data.get("data", {}).get("next_cursor", 0)
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"获取知识库失败：{e}")
                    break

            self._kb_cache = all_kbs
            logger.info(f"获取到 {len(all_kbs)} 个知识库")
            return all_kbs

    def update_note_frontmatter(self, file_path: Path, updates: Dict) -> bool:
        """更新笔记的 Frontmatter"""
        try:
            content = file_path.read_text(encoding='utf-8')

            # 解析 Frontmatter
            if not content.startswith('---'):
                logger.warning(f"{file_path} 没有 Frontmatter")
                return False

            parts = content.split('---', 2)
            if len(parts) < 3:
                logger.warning(f"{file_path} Frontmatter 格式不正确")
                return False

            frontmatter_str = parts[1]
            body = parts[2]

            # 解析 YAML
            frontmatter = yaml.safe_load(frontmatter_str) or {}

            # 更新字段
            frontmatter.update(updates)

            # 重新生成内容
            new_frontmatter = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
            new_content = f"---\n{new_frontmatter}---{body}"

            file_path.write_text(new_content, encoding='utf-8')
            return True

        except Exception as e:
            logger.error(f"更新 Frontmatter 失败 {file_path}: {e}")
            return False

    async def process_summarize(
        self,
        file_path: Path,
        api_key: str,
        minimax_key: str
    ) -> bool:
        """处理单个笔记的标题生成"""
        note_id = self.status._extract_note_id(file_path)
        if not note_id:
            logger.warning(f"无法提取笔记 ID: {file_path}")
            return False

        async with self.semaphore:
            try:
                # 读取笔记内容
                content = file_path.read_text(encoding='utf-8')

                # 提取正文内容（去掉 Frontmatter）
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        body = parts[2]
                    else:
                        body = content
                else:
                    body = content

                # 生成标题
                title = await self.generate_title(body[:3000], minimax_key)

                # 更新 Frontmatter
                updates = {
                    "summarized": True,
                    "generated_title": title,
                    "summarized_at": datetime.now().isoformat()
                }

                # 同时更新 title 字段
                for line in content.split('\n'):
                    if line.startswith('title:'):
                        old_title = line.split(':', 1)[1].strip()
                        if old_title.isdigit() or old_title == note_id:
                            updates["title"] = title
                        break

                if self.update_note_frontmatter(file_path, updates):
                    self.status.set_note_status(note_id, {
                        "summarized": True,
                        "generated_title": title
                    })
                    logger.info(f"✓ {note_id}: {title}")
                    return True
                else:
                    return False

            except Exception as e:
                logger.error(f"✗ {note_id} 处理失败：{e}")
                self.status.set_note_status(note_id, {
                    "summarize_error": str(e)
                })
                return False

    async def process_classify(
        self,
        file_path: Path,
        api_key: str,
        client_id: str,
        minimax_key: str
    ) -> bool:
        """处理单个笔记的分类"""
        note_id = self.status._extract_note_id(file_path)
        if not note_id:
            logger.warning(f"无法提取笔记 ID: {file_path}")
            return False

        async with self.semaphore:
            try:
                # 获取知识库列表
                kbs = await self.get_knowledge_bases()

                # 读取笔记内容
                content = file_path.read_text(encoding='utf-8')

                # 提取正文内容
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        body = parts[2]
                    else:
                        body = content
                else:
                    body = content

                # 分类
                result = await self.classify_note(body[:3000], kbs, minimax_key)

                # 更新 Frontmatter
                updates = {
                    "classified": True,
                    "recommended_kb": result.get("recommended_kb", ""),
                    "classification_action": result.get("action", ""),
                    "classification_confidence": result.get("confidence", ""),
                    "classification_reason": result.get("reason", ""),
                    "classified_at": datetime.now().isoformat()
                }

                if self.update_note_frontmatter(file_path, updates):
                    self.status.set_note_status(note_id, {
                        "classified": True,
                        "recommended_kb": result.get("recommended_kb", ""),
                        "action": result.get("action", "")
                    })
                    logger.info(f"✓ {note_id} -> {result.get('recommended_kb')} ({result.get('confidence')})")
                    return True
                else:
                    return False

            except Exception as e:
                logger.error(f"✗ {note_id} 分类失败：{e}")
                self.status.set_note_status(note_id, {
                    "classify_error": str(e)
                })
                return False

    async def run_summarize(self, limit: int = None, batch_size: int = 20):
        """运行批量标题生成"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 获取未处理的笔记
        unsummarized = self.status.get_unsummarized_notes(self.inbox_dir)
        logger.info(f"待处理笔记：{len(unsummarized)} 条")

        if limit:
            unsummarized = unsummarized[:limit]
            logger.info(f"限制模式：仅处理前 {limit} 条")

        if not unsummarized:
            logger.info("没有需要生成标题的笔记")
            return

        # 获取 API 密钥
        credentials = self.config.get_getnote_credentials()
        minimax_key = self.config.get_llm_api_key("minimax")

        # 批量处理
        total_batches = (len(unsummarized) + batch_size - 1) // batch_size

        for i in range(0, len(unsummarized), batch_size):
            batch = unsummarized[i:i+batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"\n批次 {batch_num}/{total_batches} (本批 {len(batch)} 条)")

            # 并发处理批次
            tasks = [
                self.process_summarize(f, credentials[0], minimax_key)
                for f in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if r is True)
            failed_count = sum(1 for r in results if r is False or isinstance(r, Exception))

            logger.info(f"  进度：{i+len(batch)}/{len(unsummarized)} (本批成功：{success_count}, 失败：{failed_count})")

            # 批次间隔
            await asyncio.sleep(3.0)

        self.status.save()
        logger.info(f"\n✅ 标题生成完成，共处理 {len(unsummarized)} 条笔记")

    async def run_classify(self, limit: int = None, batch_size: int = 20):
        """运行批量分类"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 获取未处理的笔记
        unclassified = self.status.get_unclassified_notes(self.inbox_dir)
        logger.info(f"待分类笔记：{len(unclassified)} 条")

        if limit:
            unclassified = unclassified[:limit]
            logger.info(f"限制模式：仅处理前 {limit} 条")

        if not unclassified:
            logger.info("没有需要分类的笔记")
            return

        # 获取 API 密钥
        credentials = self.config.get_getnote_credentials()
        minimax_key = self.config.get_llm_api_key("minimax")

        # 批量处理
        total_batches = (len(unclassified) + batch_size - 1) // batch_size

        for i in range(0, len(unclassified), batch_size):
            batch = unclassified[i:i+batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"\n批次 {batch_num}/{total_batches} (本批 {len(batch)} 条)")

            # 并发处理批次
            tasks = [
                self.process_classify(f, credentials[0], credentials[1], minimax_key)
                for f in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if r is True)
            failed_count = sum(1 for r in results if r is False or isinstance(r, Exception))

            logger.info(f"  进度：{i+len(batch)}/{len(unclassified)} (本批成功：{success_count}, 失败：{failed_count})")

            # 批次间隔
            await asyncio.sleep(3.0)

        self.status.save()
        logger.info(f"\n✅ 分类完成，共处理 {len(unclassified)} 条笔记")

    def get_kb_stats(self) -> dict:
        """获取分类统计信息"""
        kb_groups = {}

        for note_id, status in self.status.status.get("notes", {}).items():
            if not status.get("classified"):
                continue

            recommended_kb = status.get("recommended_kb", "未分类")
            action = status.get("classification_action", "create_new")

            key = f"{recommended_kb} ({action})"
            if key not in kb_groups:
                kb_groups[key] = {
                    "kb_name": recommended_kb,
                    "action": action,
                    "note_ids": []
                }
            kb_groups[key]["note_ids"].append(note_id)

        return kb_groups

    def _get_kb_dir(self, kb_name: str) -> Path:
        """获取知识库目录路径"""
        return self.data_dir / kb_name

    def _move_note_to_kb(self, note_file: Path, kb_dir: Path) -> bool:
        """移动笔记到知识库目录"""
        try:
            kb_dir.mkdir(parents=True, exist_ok=True)
            dest_file = kb_dir / note_file.name

            # 如果目标文件已存在，添加序号避免冲突
            if dest_file.exists():
                base_name = note_file.stem
                ext = note_file.suffix
                counter = 1
                while dest_file.exists():
                    new_name = f"{base_name}_{counter}{ext}"
                    dest_file = kb_dir / new_name
                    counter += 1

            # 移动文件
            note_file.rename(dest_file)
            logger.info(f"  ✓ 移动 {note_file.name} -> {kb_dir.name}/")
            return True
        except Exception as e:
            logger.error(f"  ✗ 移动失败 {note_file.name}: {e}")
            return False

    async def run_apply(self, limit: int = None, batch_size: int = 20, auto_confirm: bool = False):
        """执行分类 - 创建知识库并移动笔记"""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

        # 获取分类统计
        kb_groups = self.get_kb_stats()

        if not kb_groups:
            logger.info("没有已分类的笔记")
            return

        # 分离现有知识库和新知识库
        existing_kbs = set()
        new_kbs = {}

        for kb_key, group in kb_groups.items():
            kb_name = group["kb_name"]
            kb_dir = self._get_kb_dir(kb_name)

            if kb_dir.exists():
                existing_kbs.add(kb_key)
            else:
                new_kbs[kb_key] = group

        # 显示预览
        print("\n" + "=" * 60)
        print("📋 分类执行预览")
        print("=" * 60)

        print(f"\n已分类笔记组：{len(kb_groups)} 组")
        print(f"  - 使用现有知识库：{len(existing_kbs)} 组")
        print(f"  - 需要新建知识库：{len(new_kbs)} 组")

        if new_kbs and not auto_confirm:
            print("\n需要新建的知识库：")
            for kb_key, group in list(new_kbs.items())[:10]:
                print(f"  - {group['kb_name']} ({len(group['note_ids'])} 条笔记)")
            if len(new_kbs) > 10:
                print(f"  ... 还有 {len(new_kbs) - 10} 个")

        # 获取用户确认
        if not auto_confirm:
            print("\n" + "=" * 60)
            confirm = input("是否继续执行分类？(y/n): ").strip().lower()
            if confirm != "y":
                print("操作已取消")
                return

            # 对于新知识库，逐个确认
            if new_kbs:
                print("\n确认新知识库创建：")
                for kb_key, group in list(new_kbs.items()):
                    confirm_kb = input(f"  创建 '{group['kb_name']}' ? (y/n/skip-all): ").strip().lower()
                    if confirm_kb == "skip-all":
                        for k in list(new_kbs.keys())[list(new_kbs.keys()).index(kb_key):]:
                            del kb_groups[k]
                        break
                    elif confirm_kb != "y":
                        del kb_groups[kb_key]

        # 执行分类
        print("\n" + "=" * 60)
        print("开始执行分类...")
        print("=" * 60)

        moved_count = 0
        failed_count = 0
        processed_note_ids = set()

        for kb_key, group in kb_groups.items():
            kb_name = group["kb_name"]
            kb_dir = self._get_kb_dir(kb_name)

            logger.info(f"\n处理知识库：{kb_name}")

            # 创建知识库目录
            kb_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"  ✓ 知识库目录：{kb_dir}")

            # 移动笔记
            batch_num = 0
            for i in range(0, len(group["note_ids"]), batch_size):
                batch_ids = group["note_ids"][i:i+batch_size]
                batch_num += 1

                for note_id in batch_ids:
                    # 查找笔记文件
                    note_file = None
                    for ext in ["", ".md"]:
                        candidate = self.inbox_dir / f"{note_id}*.md"
                        matches = list(self.inbox_dir.glob(f"{note_id}*.md"))
                        if matches:
                            note_file = matches[0]
                            break

                    if not note_file:
                        logger.warning(f"  ⚠ 未找到笔记文件：{note_id}")
                        continue

                    if self._move_note_to_kb(note_file, kb_dir):
                        moved_count += 1
                        processed_note_ids.add(note_id)

                        # 更新状态
                        self.status.set_note_status(note_id, {
                            "moved_to_kb": kb_name,
                            "moved_at": datetime.now().isoformat()
                        })
                    else:
                        failed_count += 1

                # 批次间隔
                await asyncio.sleep(0.5)

            logger.info(f"  完成：{kb_name} ({len(batch_ids)} 条)")

        self.status.save()

        print("\n" + "=" * 60)
        print("✅ 分类执行完成")
        print("=" * 60)
        print(f"  移动笔记：{moved_count} 条")
        print(f"  失败：{failed_count} 条")
        print(f"  创建/更新知识库：{len(kb_groups)} 个")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="散落笔记批量处理脚本")
    parser.add_argument("--summarize", action="store_true", help="生成标题")
    parser.add_argument("--classify", action="store_true", help="分类笔记")
    parser.add_argument("--apply", action="store_true", help="执行分类（创建知识库并移动笔记）")
    parser.add_argument("--limit", type=int, help="限制处理数量（测试用）")
    parser.add_argument("--batch-size", type=int, default=20, help="每批处理数量")
    parser.add_argument("--auto-confirm", action="store_true", help="自动确认新知识库创建（无需逐个确认）")

    args = parser.parse_args()

    config = Config()
    processor = NoteProcessor(config)

    if args.summarize:
        await processor.run_summarize(limit=args.limit, batch_size=args.batch_size)
    elif args.classify:
        await processor.run_classify(limit=args.limit, batch_size=args.batch_size)
    elif args.apply:
        await processor.run_apply(limit=args.limit, batch_size=args.batch_size, auto_confirm=args.auto_confirm)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
