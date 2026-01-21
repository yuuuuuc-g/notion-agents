"""
utils/logger.py
Standard logging configuration for the Notion-Prism-React project.
"""

import logging
import sys
from typing import Optional

# Default log format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# Configure root logger
def setup_logger(
    name: str = "notion_prism",
    level: int = logging.INFO,
    format_str: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    stream: Optional[logging.Handler] = None,
) -> logging.Logger:
    """
    Configure and return a logger with the given settings.

    Args:
        name: Logger name (usually __name__ of the calling module)
        level: Logging level (default: INFO)
        format_str: Format string for log messages
        date_format: Date format for timestamps
        stream: Optional stream handler (default: sys.stdout)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(format_str, date_format)

    # Create console handler
    if stream is None:
        stream = logging.StreamHandler(sys.stdout)

    stream.setFormatter(formatter)
    logger.addHandler(stream)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger


# Create default logger for the project
logger = setup_logger()


# Convenience functions for quick imports
def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return setup_logger(name)


# Example usage:
# from utils.logger import get_logger
# logger = get_logger(__name__)
#
# logger.info("This is an info message")
# logger.error("This is an error message")
