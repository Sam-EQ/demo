"""FastAPI app entry point."""
import shutil
import subprocess
from fastapi import FastAPI
from loguru import logger
from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging


def validate_dependencies() -> None:
    """Check ffmpeg, ffprobe, and API key at startup."""
    errors = []
    
    # ffmpeg check
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        errors.append("ffmpeg not in PATH")
    else:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            if result.returncode != 0:
                errors.append("ffmpeg found but not working")
            else:
                logger.info(f"ffmpeg OK: {ffmpeg_path}")
        except Exception as e:
            errors.append(f"ffmpeg check failed: {e}")
    
    # ffprobe check
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        errors.append("ffprobe not in PATH")
    else:
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            if result.returncode != 0:
                errors.append("ffprobe found but not working")
            else:
                logger.info(f"ffprobe OK: {ffprobe_path}")
        except Exception as e:
            errors.append(f"ffprobe check failed: {e}")
    
    # API key check
    if not settings.OPENAI_API_KEY or not settings.OPENAI_API_KEY.strip():
        errors.append("OPENAI_API_KEY not set")
    else:
        logger.info("API key present")
    
    if errors:
        error_msg = "Startup validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def create_app() -> FastAPI:
    configure_logging()
    validate_dependencies()
    
    app = FastAPI(
        title="Audio Transcription & Translation Service",
        description="Production-ready backend for audio transcription and translation using OpenAI APIs",
        version="1.0.0"
    )
    
    app.include_router(api_router, prefix="/api", tags=["transcription"])
    
    logger.info("App started")
    return app


app = create_app()
