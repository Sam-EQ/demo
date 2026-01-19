"""Structured logging configuration using loguru."""
import sys
import json
from loguru import logger
from app.core.config import settings


def configure_logging() -> None:
    """Configure loguru logger with structured JSON output."""
    logger.remove()
    
    # Configure structured JSON logging
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
        serialize=False,  # Use readable format instead of pure JSON for better debugging
    )
