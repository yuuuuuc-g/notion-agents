"""
middleware/bandwidth_limiter.py
应用层带宽限流器
功能：限制每个 IP 在单位时间内的总上传流量，防止资源耗尽攻击
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class BandwidthLimiter:
    def __init__(self, max_mb_per_minute: int = 100):
        """
        Args:
            max_mb_per_minute: 每分钟最大上传量 (MB)
        """
        self.max_bytes = max_mb_per_minute * 1024 * 1024
        # 使用 defaultdict 存储每个 IP 的使用情况
        # 结构: IP -> {'bytes': 已用字节, 'reset': 重置时间}
        self.usage = defaultdict(
            lambda: {"bytes": 0, "reset": datetime.now() + timedelta(minutes=1)}
        )

    async def check(self, client_ip: str, size_bytes: int):
        """
        检查本次请求是否会超出带宽限制
        """
        now = datetime.now()
        record = self.usage[client_ip]

        # 1. 检查窗口是否过期，过期则重置
        if now > record["reset"]:
            record["bytes"] = 0
            record["reset"] = now + timedelta(minutes=1)

        # 2. 检查累加后是否超限
        if record["bytes"] + size_bytes > self.max_bytes:
            wait_seconds = (record["reset"] - now).seconds
            logger.warning(
                f"⚠️ Bandwidth limit exceeded for IP {client_ip}. Used: {record['bytes']/1024/1024:.2f}MB"
            )
            raise HTTPException(
                status_code=429,
                detail=f"带宽限制已达到 (Bandwidth Limit Exceeded). 请等待 {wait_seconds} 秒后重试。",
            )

        # 3. 记录本次使用量
        record["bytes"] += size_bytes
        # logger.debug(f"IP {client_ip} used {size_bytes} bytes. Total: {record['bytes']}/{self.max_bytes}")
