"""FastAPI application entry point."""
import shutil
import subprocess
from fastapi import FastAPI
from loguru import logger
from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging


def validate_dependencies() -> None:
    """
    Validate that all required dependencies are available at startup.
    Fails fast with clear error messages if any dependency is missing.
    
    Raises:
        RuntimeError: If any required dependency is missing
    """
    errors = []
    
    # Check FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        errors.append("ffmpeg not found in PATH. Please install FFmpeg and ensure it's available in your PATH.")
    else:
        try:
            # Verify ffmpeg is executable
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            if result.returncode != 0:
                errors.append("ffmpeg found but not executable or returned an error.")
            else:
                logger.info(f"FFmpeg validated: {ffmpeg_path}")
        except Exception as e:
            errors.append(f"Failed to execute ffmpeg: {e}")
    
    # Check FFprobe
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        errors.append("ffprobe not found in PATH. Please install FFmpeg (ffprobe is included) and ensure it's available in your PATH.")
    else:
        try:
            # Verify ffprobe is executable
            result = subprocess.run(
                ["ffprobe", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False
            )
            if result.returncode != 0:
                errors.append("ffprobe found but not executable or returned an error.")
            else:
                logger.info(f"FFprobe validated: {ffprobe_path}")
        except Exception as e:
            errors.append(f"Failed to execute ffprobe: {e}")
    
    # Check OpenAI API key
    if not settings.OPENAI_API_KEY or not settings.OPENAI_API_KEY.strip():
        errors.append("OPENAI_API_KEY environment variable is not set or is empty.")
    else:
        logger.info("OpenAI API key validated (present and non-empty)")
    
    # Fail fast if any validation failed
    if errors:
        error_message = "Startup dependency validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        logger.error(error_message)
        raise RuntimeError(error_message)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Configure logging first
    configure_logging()
    
    # Validate dependencies at startup (fail fast)
    validate_dependencies()
    
    # Create FastAPI app
    app = FastAPI(
        title="Audio Transcription & Translation Service",
        description="Production-ready backend for audio transcription and translation using OpenAI APIs",
        version="1.0.0"
    )
    
    # Include API router
    app.include_router(api_router, prefix="/api", tags=["transcription"])
    
    logger.info("Application started successfully with all dependencies validated")
    
    return app


app = create_app()
