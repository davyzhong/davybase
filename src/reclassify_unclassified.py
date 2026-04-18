#!/usr/bin/env python3
"""
未分类笔记二次分类脚本

将 processed/未分类/ 中的笔记重新分类到新的知识库目录：
- AI 与编程
- 企业管理
- 财务与会计
- 跨境物流
- 人文历史
- 个人成长
- 编程+AI（现有）
- AI+ 机器学习（现有）
- 产品管理（现有）
- 系统架构（现有）
- 后端开发（现有）
- 前端开发（现有）
- 数据库（现有）
- DevOps（现有）
- 经营&管理（现有）
- 学习&思考（现有）
"""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import itertools

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.llm_providers.qwen import QwenProvider
from src.llm_providers.base import LLMProvider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger("davybase.reclassify")

# 新的分类体系（16 个知识库）
VALID_CATEGORIES = [
    # 新增知识库（6 个）
    "AI 与编程",
    "企业管理",
    "财务与会计",
    "跨境物流",
    "人文历史",
    "个人成长",

    # 现有知识库（10 个）
    "编程+AI",
    "AI+ 机器学习",
    "产品管理",
    "系统架构",
    "后端开发",
    "前端开发",
    "数据库",
    "DevOps",
    "经营&管理",
    "学习&思考",
]

# 二次分类提示词（优化版）
RECLASSIFY_PROMPT = """你是一个知识库分类专家。请阅读以下笔记内容，然后以 JSON 格式返回分类结果。

## 分类体系（必须从以下 16 个中选择一个）：

**新增知识库（6 个）**:
- AI 与编程：AI 编程工具（Claude Code/Cursor/n8n）、MCP 协议、开发范式、效率工具
- 企业管理：业务管理、团队建设、组织变革、经营分析、领导力
- 财务与会计：财务报表、财务分析、管理会计、税务、审计
- 跨境物流：国际快递、面单系统、结算系统、供应链、物流业务架构
- 人文历史：历史典故、哲学思想、文化教育、国学经典
- 个人成长：人生感悟、学习方法、心理健康、职业发展

**现有知识库（10 个）**:
- 编程+AI：编程与 AI 交叉内容
- AI+ 机器学习：人工智能算法、机器学习、深度学习
- 产品管理：产品设计、产品规划、竞品分析
- 系统架构：系统设计与架构
- 后端开发：后端技术、服务器端开发
- 前端开发：前端技术、Web 开发、UI
- 数据库：数据库技术、SQL、NoSQL
- DevOps：运维开发、CI/CD、容器化
- 经营&管理：企业经营、管理方法论
- 学习&思考：学习方法、思考模型

## 分类规则：
1. 优先使用新增的 6 个知识库（更精确）
2. 如果内容同时符合多个分类，选择最具体的那个
3. 技术实现细节 → 对应技术库（如后端开发、前端开发）
4. 业务/流程/架构 → 对应业务库（如跨境物流、企业管理）
5. 个人感悟/通用知识 → 人文历史或个人成长

## 笔记内容：
{content}

## 返回格式（只返回 JSON，不要任何其他内容）：
{{"category": "分类名称", "confidence": "high", "reason": "简短的分类理由（20 字以内）"}}
"""


class UnclassifiedReclassifier:
    """未分类笔记二次分类器"""

    def __init__(self, config: Config):
        self.config = config
        self.processed_dir = Path(config.data_path)
        self.unclassified_dir = self.processed_dir / "未分类"

        # 初始化多个 LLM Providers（主用千问）
        self.providers = []

        # 千问 API（主力）
        try:
            qwen_key = config.get_llm_api_key("qwen")
            if qwen_key:
                # 添加两个千问实例以增加并发
                self.providers.append(("qwen-1", QwenProvider(api_key=qwen_key)))
                self.providers.append(("qwen-2", QwenProvider(api_key=qwen_key)))
                logger.info("已初始化 2 个千问 Provider 实例（增加并发）")
        except Exception as e:
            logger.warning(f"千问 API 初始化失败：{e}")

        if not self.providers:
            raise RuntimeError("没有可用的 LLM Provider")

        # Round-robin 迭代器
        self.provider_cycle = itertools.cycle(self.providers)

        # 统计信息
        self.stats = {
            "total": 0,
            "reclassified": 0,
            "failed": 0,
            "by_category": {},
            "by_provider": {}
        }

    def read_note_content(self, filepath: Path) -> str:
        """读取笔记内容"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read(3000)  # 只读取前 3000 字符

    def get_category_dir(self, category: str) -> Path:
        """获取分类对应的目录路径"""
        return self.processed_dir / category

    def move_note_to_category(self, note_file: Path, category: str) -> bool:
        """将笔记移动到指定分类目录"""
        try:
            target_dir = self.get_category_dir(category)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / note_file.name

            shutil.move(str(note_file), str(target_path))
            return True
        except Exception as e:
            logger.error(f"移动笔记失败：{note_file.name} -> {category}: {e}")
            return False

    def get_next_provider(self) -> Tuple[str, LLMProvider]:
        """获取下一个 Provider（round-robin）"""
        return next(self.provider_cycle)

    async def classify_single_note(self, filepath: Path, content: str, provider_name: str, provider) -> Dict:
        """分类单条笔记"""
        try:
            prompt = RECLASSIFY_PROMPT.format(content=content)
            response = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            # 解析 JSON 响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            # 处理空响应
            if not response:
                logger.warning(f"[{provider_name}] 空响应，使用备用分类")
                return {
                    "success": True,
                    "category": "未分类",
                    "confidence": "low",
                    "reason": "API 返回空响应",
                    "provider": provider_name
                }

            result = json.loads(response)
            category = result.get("category", "未分类")

            # 验证分类是否有效
            if category not in VALID_CATEGORIES:
                logger.warning(f"无效分类 '{category}'，使用'未分类'代替")
                category = "未分类"

            return {
                "success": True,
                "category": category,
                "confidence": result.get("confidence", "low"),
                "reason": result.get("reason", ""),
                "provider": provider_name
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败 {filepath.name} ({provider_name}): {e}")
            # JSON 解析失败时使用备用分类
            return {
                "success": True,
                "category": "未分类",
                "confidence": "low",
                "reason": f"JSON 解析失败：{e}",
                "provider": provider_name
            }
        except Exception as e:
            logger.error(f"分类失败 {filepath.name} ({provider_name}): {e}")
            return {
                "success": False,
                "category": "未分类",
                "confidence": "low",
                "reason": str(e),
                "provider": provider_name
            }

    async def run(self, limit: int = None, dry_run: bool = False):
        """执行二次分类

        Args:
            limit: 限制处理的笔记数量（None=全部）
            dry_run: 预览模式（不实际移动）
        """
        # 获取所有未分类笔记
        if not self.unclassified_dir.exists():
            logger.error(f"未分类目录不存在：{self.unclassified_dir}")
            return

        note_files = list(self.unclassified_dir.glob("*.md"))
        if limit:
            note_files = note_files[:limit]

        self.stats["total"] = len(note_files)
        logger.info(f"扫描到 {len(note_files)} 条未分类笔记")
        logger.info(f"可用 Provider: {[name for name, _ in self.providers]}")

        if dry_run:
            logger.info("预览模式：不会实际移动文件")

        # 并发配置
        per_provider_concurrency = 12  # 每个 provider 实例最多 12 个并发请求
        semaphores = {name: asyncio.Semaphore(per_provider_concurrency) for name, _ in self.providers}
        processed = 0
        progress_lock = asyncio.Lock()

        async def classify_with_semaphore(filepath: Path) -> dict:
            """带信号量控制的分类函数"""
            nonlocal processed

            # 获取下一个 provider（round-robin 分配）
            provider_name, provider = self.get_next_provider()
            semaphore = semaphores[provider_name]

            async with semaphore:
                content = self.read_note_content(filepath)
                result = await self.classify_single_note(filepath, content, provider_name, provider)

                async with progress_lock:
                    processed += 1

                    # Provider 统计
                    provider_key = f"{provider_name}_success" if result.get("success") else f"{provider_name}_failed"
                    self.stats["by_provider"][provider_key] = self.stats["by_provider"].get(provider_key, 0) + 1

                    if not result.get("success"):
                        self.stats["failed"] += 1
                    else:
                        category = result["category"]
                        self.stats["by_category"][category] = self.stats["by_category"].get(category, 0) + 1
                        self.stats["reclassified"] += 1

                        if not dry_run:
                            success = self.move_note_to_category(filepath, category)
                            if success:
                                logger.info(f"[{processed}/{len(note_files)}] ✓ {filepath.name} -> {category} ({provider_name})")
                            else:
                                self.stats["failed"] += 1
                        else:
                            logger.info(f"[预览] {filepath.name} -> {category} ({provider_name})")

                    # 每 50 条报告进度
                    if processed % 50 == 0:
                        logger.info(f"进度：{processed}/{len(note_files)} ({processed/len(note_files)*100:.1f}%)")

                return result

        # 创建所有任务并发执行
        tasks = [classify_with_semaphore(filepath) for filepath in note_files]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 最终进度报告
        logger.info(f"进度：{processed}/{len(note_files)} ({processed/len(note_files)*100:.1f}%)")

        # 最终统计
        logger.info("=" * 70)
        logger.info("二次分类完成!")
        logger.info(f"总计：{self.stats['total']} 条")
        logger.info(f"成功：{self.stats['reclassified']} 条")
        logger.info(f"失败：{self.stats['failed']} 条")
        logger.info("分类分布:")
        for cat, count in sorted(self.stats["by_category"].items(), key=lambda x: -x[1]):
            logger.info(f"  {cat}: {count} 条")
        logger.info("Provider 统计:")
        # 合并相同基础 provider 的统计（如 qwen-1 和 qwen-2 合并为 qwen）
        provider_totals = {}
        for provider_name, _ in self.providers:
            base_name = provider_name.split('-')[0]  # qwen-1 -> qwen
            if base_name not in provider_totals:
                provider_totals[base_name] = {"success": 0, "failed": 0}
            provider_totals[base_name]["success"] += self.stats["by_provider"].get(f"{provider_name}_success", 0)
            provider_totals[base_name]["failed"] += self.stats["by_provider"].get(f"{provider_name}_failed", 0)

        for base_name, totals in provider_totals.items():
            logger.info(f"  {base_name}: 成功 {totals['success']} 条，失败 {totals['failed']} 条")
        logger.info("=" * 70)

        return self.stats


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="未分类笔记二次分类脚本")
    parser.add_argument("--limit", type=int, default=None, help="限制处理数量（用于测试）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（不实际移动）")
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")

    args = parser.parse_args()

    config = Config(config_path=args.config)
    reclassifier = UnclassifiedReclassifier(config)

    await reclassifier.run(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
