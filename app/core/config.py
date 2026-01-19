"""Configuration management using Pydantic BaseSettings."""
import os
from typing import List
from pydantic import Field, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY", description="OpenAI API key for transcription and translation")
    TEMP_DIR: str = Field("/tmp/audio_processing", env="TEMP_DIR", description="Directory for temporary audio files")
    MAX_AUDIO_DURATION_SECONDS: float = Field(300.0, env="MAX_AUDIO_DURATION_SECONDS", description="Maximum allowed audio duration in seconds")
    MAX_FILE_SIZE_BYTES: int = Field(10 * 1024 * 1024, env="MAX_FILE_SIZE_BYTES", description="Maximum file size in bytes (default: 10MB)")
    CHUNK_MAX_LENGTH_SECONDS: float = Field(60.0, env="CHUNK_MAX_LENGTH_SECONDS", description="Maximum length of audio chunks in seconds")
    TARGET_LANGUAGE: str = Field("en", env="TARGET_LANGUAGE", description="Default target language for translation")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    TRANSCRIPTION_MODEL: str = Field("whisper-1", env="TRANSCRIPTION_MODEL", description="OpenAI transcription model (whisper-1 or gpt-4o-transcribe)")
    TRANSLATION_MODEL: str = Field("gpt-4o-mini", env="TRANSLATION_MODEL", description="OpenAI translation model")

    SUPPORTED_LANGUAGES: List[str] = ["en", "da", "fr", "pt", "zh-Hans"]

    @validator("TARGET_LANGUAGE")
    def validate_target_language(cls, v: str, values: dict) -> str:
        """Validate that target language is in the supported languages list."""
        supported = values.get("SUPPORTED_LANGUAGES", [])
        if v not in supported:
            raise ValueError(f"TARGET_LANGUAGE '{v}' is not supported. Supported languages: {supported}")
        return v

    @validator("TRANSCRIPTION_MODEL")
    def validate_transcription_model(cls, v: str) -> str:
        """Validate transcription model name."""
        allowed_models = ["whisper-1", "gpt-4o-transcribe"]
        if v not in allowed_models:
            raise ValueError(f"TRANSCRIPTION_MODEL '{v}' is not supported. Allowed models: {allowed_models}")
        return v

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
