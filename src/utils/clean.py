import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def cleanup_directory(path: Path):
    try:
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Cleaned up directory: {path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup {path}: {e}")
