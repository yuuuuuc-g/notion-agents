"""
middleware/error_handler.py
统一错误处理中间件 (Pro Version)
功能：
1. 提供标准化的错误响应格式 (ErrorResponse)
2. 统一捕获 HTTP, Validation, RateLimit, 业务逻辑 和 未知异常
3. 提供注册辅助函数，净化 server.py
"""
import os
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorResponse:
    """标准错误响应实体"""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict = None,
        status_code: int = 500,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self, include_details: bool = True) -> dict:
        response = {
            "status": "error",
            "code": self.error_code,
            "message": self.message,
        }
        if include_details and self.details:
            response["details"] = self.details
        return response


# === 具体的处理函数 ===


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """处理标准 HTTP 异常 (404, 403, etc)"""
    if exc.status_code >= 500:
        logger.error(
            f"🔥 HTTP {exc.status_code}: {exc.detail} | Path: {request.url.path}"
        )
    else:
        logger.warning(
            f"⚠️ HTTP {exc.status_code}: {exc.detail} | Path: {request.url.path}"
        )

    error = ErrorResponse(
        error_code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        details={"path": str(request.url.path)},
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content=error.to_dict())


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理参数验证错误 (422)"""
    errors = []
    for error in exc.errors():
        # 简化 Pydantic 的错误信息
        # loc 通常是 ('body', 'query', etc)
        loc_str = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({"field": loc_str, "msg": error["msg"]})

    logger.warning(f"⚠️ Validation Error: {errors} | Path: {request.url.path}")

    error = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Invalid request parameters",
        details={"errors": errors},
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error.to_dict()
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """处理限流异常 (429)"""
    client_ip = request.client.host if request.client else "unknown"
    logger.warning(f"🚫 Rate Limit Exceeded: IP={client_ip} | Limit={exc.detail}")

    error = ErrorResponse(
        error_code="RATE_LIMIT_EXCEEDED",
        message="Too many requests, please try again later.",
        details={"retry_after": "60 seconds", "limit": str(exc.detail)},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=error.to_dict()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理所有未捕获的异常 (500)"""
    logger.error(f"💥 Unhandled Exception: {exc}", exc_info=True)

    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    message = (
        "Internal Server Error"
        if is_production
        else f"{type(exc).__name__}: {str(exc)}"
    )
    details = {}
    if not is_production:
        details["traceback"] = traceback.format_exc().splitlines()[-5:]  # 只返回最后5行堆栈

    error = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message=message,
        details=details,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error.to_dict()
    )


# === 自定义业务异常 ===
class BusinessException(Exception):
    """
    通用业务异常
    用于在 Service 层主动抛出可控的错误
    """

    def __init__(
        self, message: str, code: str = "BUSINESS_ERROR", status_code: int = 400
    ):
        self.message = message
        self.code = code
        self.status_code = status_code


async def business_exception_handler(
    request: Request, exc: BusinessException
) -> JSONResponse:
    """处理业务逻辑异常"""
    logger.warning(f"⚠️ Business Logic Error: {exc.code} - {exc.message}")
    error = ErrorResponse(
        error_code=exc.code, message=exc.message, status_code=exc.status_code
    )
    return JSONResponse(status_code=exc.status_code, content=error.to_dict())


# === 🔥 核心：统一注册入口 ===
def register_exception_handlers(app: FastAPI):
    """
    一键注册所有异常处理器
    推荐在 server.py 中调用此函数，替代手动的 add_exception_handler
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("🛡️ Exception Handlers Registered (Pro Mode)")


# === 兼容性别名 ===
# 你的 server.py 目前引用的是 global_exception_handler
# 这里的别名确保 server.py 不会因为找不到名字而报错
global_exception_handler = general_exception_handler
