"""
utils/logger.py
Standard logging configuration for the Notion-Prism-React project.
修复：添加 setup_logging 函数以支持 server.py 的全局初始化调用。
"""

import logging
import sys
from typing import Optional

# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    """
    Global logging initialization.
    Configures the Root Logger so that all subsequent get_logger calls
    inherit this configuration.

    Used by server.py at startup.
    """
    # 使用 basicConfig 配置 Root Logger
    # 这样所有没有特定 Handler 的子 Logger 都会使用这个配置
    logging.basicConfig(
        level=logging.INFO,
        format=DEFAULT_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        stream=sys.stdout,
    )

    # 可以在这里屏蔽一些嘈杂的第三方库日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def setup_logger(
    name: str = "notion_prism",
    level: int = logging.INFO,
    format_str: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    stream: Optional[logging.Handler] = None,
) -> logging.Logger:
    """
    Configure and return a specific logger with the given settings.

    Args:
        name: Logger name
        level: Logging level
        format_str: Format string
        date_format: Date format
        stream: Optional handler

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times if already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Only add handler if verify propagation is not enough
    # or if we need specific formatting for this logger
    if not logger.handlers:
        formatter = logging.Formatter(format_str, date_format)

        if stream is None:
            stream = logging.StreamHandler(sys.stdout)

        stream.setFormatter(formatter)
        logger.addHandler(stream)

    # Prevent propagation if we have our own handler attached
    # to avoid duplicate logs in Root Logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    If setup_logging() has been called, this logger will inherit root settings
    unless setup_logger() is used to customize it.
    """
    return logging.getLogger(name)
