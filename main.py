"""FastAPI application entry point."""
from fastapi import FastAPI
from app.api.routes import router as api_router
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Configure logging first
    configure_logging()
    
    # Create FastAPI app
    app = FastAPI(
        title="Audio Transcription & Translation Service",
        description="Production-ready backend for audio transcription and translation using OpenAI APIs",
        version="1.0.0"
    )
    
    # Include API router
    app.include_router(api_router, prefix="/api", tags=["transcription"])
    
    return app


app = create_app()
