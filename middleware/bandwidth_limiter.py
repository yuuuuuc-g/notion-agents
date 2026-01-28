"""
middleware/bandwidth_limiter.py
带宽限制器：融合版
特性：
1. 核心逻辑 (BandwidthLimiter): 采用你的版本 (defaultdict + 友好报错)
2. 中间件封装 (BandwidthLimiterMiddleware): 补充缺失的 FastAPI 集成类
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class BandwidthLimiter:
    """
    [核心逻辑层]
    功能：限制每个 IP 在单位时间内的总上传流量
    优点：使用 defaultdict 简化逻辑，提供友好的等待时间提示
    """

    def __init__(self, max_mb_per_minute: int = 100):
        """
        Args:
            max_mb_per_minute: 每分钟最大上传量 (MB)
        """
        self.max_bytes = max_mb_per_minute * 1024 * 1024
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
            wait_seconds = int((record["reset"] - now).total_seconds())
            # 防止极少数情况下计算出负数
            if wait_seconds < 0:
                wait_seconds = 0

            logger.warning(
                f"⚠️ Bandwidth limit exceeded for IP {client_ip}. Used: {record['bytes'] / 1024 / 1024:.2f}MB"
            )
            raise HTTPException(
                status_code=429,
                detail=f"带宽限制已达到. 请等待 {wait_seconds} 秒后重试。",
            )

        # 3. 记录本次使用量
        record["bytes"] += size_bytes
        # logger.debug(f"IP {client_ip} used {size_bytes} bytes")


class BandwidthLimiterMiddleware(BaseHTTPMiddleware):
    """
    [中间件封装层]
    功能：将 BandwidthLimiter 集成到 FastAPI 的全局请求处理流中
    作用：Server.py 需要导入此类来拦截所有请求
    """

    def __init__(self, app: ASGIApp, max_bandwidth_mb: int = 50):
        super().__init__(app)
        # 初始化核心逻辑实例
        self.limiter = BandwidthLimiter(max_mb_per_minute=max_bandwidth_mb)

    async def dispatch(self, request: Request, call_next):
        """
        中间件拦截逻辑
        """
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"

        # 尝试从 Header 获取内容长度 (Content-Length)
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)

                # 调用核心逻辑进行检查
                await self.limiter.check(client_ip, size)
            except ValueError:
                # Content-Length 格式错误，忽略或记录日志
                pass

        # 如果未超限，继续处理后续请求
        response = await call_next(request)
        return response
