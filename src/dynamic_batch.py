#!/usr/bin/env python3
"""
动态批次调度器

根据 Worker 处理速度和限流情况，动态调整批次大小，实现负载均衡。

Usage:
    scheduler = DynamicBatchScheduler(worker_configs, strategy="threshold")
    batch_size = scheduler.get_batch_size("qwen")
    new_batch = scheduler.record_success("qwen", num_notes=2, duration=5.0)
    new_batch = scheduler.record_rate_limit("qwen")
"""
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, List
import time
import logging

logger = logging.getLogger("davybase.dynamic_batch")


@dataclass
class WorkerStats:
    """Worker 性能统计"""

    window_size: int = 10
    processing_times: deque = field(default_factory=lambda: deque(maxlen=10))
    rate_limit_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_adjustment_time: float = 0.0

    def record_processing(self, num_notes: int, duration: float):
        """记录一次处理"""
        time_per_note = duration / num_notes if num_notes > 0 else 10.0
        self.processing_times.append(time_per_note)
        self.last_adjustment_time = time.time()

    @property
    def avg_time_per_note(self) -> float:
        """平均每条笔记处理时间（秒）"""
        if not self.processing_times:
            return 10.0
        return sum(self.processing_times) / len(self.processing_times)

    @property
    def notes_per_second(self) -> float:
        """处理速度（条/秒）"""
        avg_time = self.avg_time_per_note
        return 1.0 / avg_time if avg_time > 0 else 0.1


class DynamicBatchScheduler:
    """动态批次调度器

    根据 Worker 处理速度和限流情况，动态调整批次大小。

    支持两种策略:
    - threshold: 阈值模式（稳健），速度超过平均 20% 才增加批次
    - aggressive: 激进模式，速度快就增加，慢就减少
    """

    def __init__(
        self,
        worker_configs: List[dict],
        strategy: str = "threshold",
        min_batch_size: int = 1,
        max_batch_size: int = 10,
        adjustment_window: int = 10,
        speed_threshold: float = 1.2,
        rate_limit_decay: float = 0.5,
        cooldown_seconds: float = 30.0,  # 调整冷却时间
    ):
        self.worker_stats: Dict[str, WorkerStats] = {}
        self.current_batch: Dict[str, int] = {}

        for wc in worker_configs:
            name = wc["name"]
            self.worker_stats[name] = WorkerStats(window_size=adjustment_window)
            self.current_batch[name] = wc.get("batch_size", 2)

        self.strategy = strategy
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.speed_threshold = speed_threshold
        self.rate_limit_decay = rate_limit_decay
        self.cooldown_seconds = cooldown_seconds

    def get_batch_size(self, worker_name: str) -> int:
        """获取当前批次大小"""
        return self.current_batch.get(worker_name, 2)

    def record_success(
        self,
        worker_name: str,
        num_notes: int,
        duration: float
    ) -> int:
        """记录成功处理，返回新的批次大小"""
        stats = self.worker_stats[worker_name]
        stats.record_processing(num_notes, duration)
        stats.success_count += 1

        # 检查冷却时间
        if time.time() - stats.last_adjustment_time < self.cooldown_seconds:
            return self.current_batch[worker_name]

        new_batch = self._adjust_batch(worker_name)
        if new_batch != self.current_batch[worker_name]:
            self.current_batch[worker_name] = new_batch
            stats.last_adjustment_time = time.time()
            logger.info(
                f"[{worker_name}] 批次调整：{self.get_batch_size(worker_name) - (1 if new_batch < self.current_batch[worker_name] else -1)}→{new_batch} "
                f"(速度={stats.notes_per_second:.2f}条/秒)"
            )
        return new_batch

    def record_rate_limit(self, worker_name: str) -> int:
        """记录限流触发，返回新的批次大小（立即调整，不受冷却时间限制）"""
        stats = self.worker_stats[worker_name]
        stats.rate_limit_count += 1

        # 限流时直接减少批次
        current = self.current_batch[worker_name]
        if self.strategy == "aggressive":
            new_batch = max(self.min_batch_size, current - 2)
        else:  # threshold
            decay = int(current * self.rate_limit_decay)
            new_batch = max(self.min_batch_size, current - max(1, decay))

        if new_batch != current:
            self.current_batch[worker_name] = new_batch
            stats.last_adjustment_time = time.time()
            logger.warning(
                f"[{worker_name}] 触发限流 (累计{stats.rate_limit_count}次)，批次调整：{current}→{new_batch}"
            )
        return new_batch

    def record_failure(self, worker_name: str) -> None:
        """记录失败"""
        stats = self.worker_stats[worker_name]
        stats.fail_count += 1

    def get_status(self) -> Dict[str, dict]:
        """获取所有 Worker 的状态"""
        status = {}
        for name, stats in self.worker_stats.items():
            status[name] = {
                "batch_size": self.current_batch[name],
                "notes_per_second": round(stats.notes_per_second, 2),
                "avg_time_per_note": round(stats.avg_time_per_note, 2),
                "success_count": stats.success_count,
                "fail_count": stats.fail_count,
                "rate_limit_count": stats.rate_limit_count,
            }
        return status

    def _adjust_batch(self, worker_name: str) -> int:
        """根据速度调整批次"""
        current = self.current_batch[worker_name]
        stats = self.worker_stats[worker_name]

        # 计算所有 Worker 的平均速度
        all_speeds = [s.notes_per_second for s in self.worker_stats.values()]
        if not all_speeds:
            return current

        overall_avg = sum(all_speeds) / len(all_speeds)
        my_speed = stats.notes_per_second

        if self.strategy == "aggressive":
            # 激进模式：速度快就增加
            if my_speed > overall_avg:
                return min(self.max_batch_size, current + 1)
            elif my_speed < overall_avg * 0.8:
                return max(self.min_batch_size, current - 1)
        else:  # threshold
            # 阈值模式：需要显著快于平均才增加
            if my_speed > overall_avg * self.speed_threshold:
                return min(self.max_batch_size, current + 1)
            elif my_speed < overall_avg * (1 / self.speed_threshold):
                return max(self.min_batch_size, current - 1)

        return current
