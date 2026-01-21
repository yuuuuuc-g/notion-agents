"""
middleware/metrics.py
Prometheus 监控中间件
功能：自动记录所有请求的耗时、计数和状态码
✅ 修复版：metrics_endpoint 增加 request 参数
"""
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# === 1. 定义指标 (Metrics) ===

# 计数器：记录请求总数
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests count", ["method", "endpoint", "status"]
)

# 直方图：记录请求耗时分布 (秒)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)


# === 2. 定义中间件类 ===
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 默认状态码
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            raise
        finally:
            process_time = time.time() - start_time

            method = request.method
            endpoint = request.url.path

            # 过滤掉监控接口本身，防止噪音
            if endpoint not in ["/metrics", "/health", "/favicon.ico"]:
                REQUEST_COUNT.labels(
                    method=method, endpoint=endpoint, status=status_code
                ).inc()

                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                    process_time
                )


# === 3. 暴露数据的处理函数 ===
# ✅ 修复点：增加 request 参数，虽然我们不使用它，但 Starlette 路由需要它
def metrics_endpoint(request: Request):
    """
    /metrics 接口的处理函数
    Prometheus 服务器会来这里拉取数据
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
