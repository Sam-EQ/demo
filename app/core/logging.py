"""Logging setup."""
import sys
from loguru import logger
from app.core.config import settings


def configure_logging() -> None:
    """Setup loguru."""
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
    )
