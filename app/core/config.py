"""App configuration."""
from typing import List
from pydantic import Field, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    TEMP_DIR: str = Field("/tmp/audio_processing", env="TEMP_DIR")
    MAX_AUDIO_DURATION_SECONDS: float = Field(300.0, env="MAX_AUDIO_DURATION_SECONDS")
    MAX_FILE_SIZE_BYTES: int = Field(10 * 1024 * 1024, env="MAX_FILE_SIZE_BYTES")  # 10MB
    CHUNK_MAX_LENGTH_SECONDS: float = Field(60.0, env="CHUNK_MAX_LENGTH_SECONDS")
    TARGET_LANGUAGE: str = Field("en", env="TARGET_LANGUAGE")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    TRANSCRIPTION_MODEL: str = Field("whisper-1", env="TRANSCRIPTION_MODEL")
    TRANSLATION_MODEL: str = Field("gpt-4o-mini", env="TRANSLATION_MODEL")

    SUPPORTED_LANGUAGES: List[str] = ["en", "da", "fr", "pt", "zh-Hans"]

    @validator("TARGET_LANGUAGE")
    def validate_target_language(cls, v: str, values: dict) -> str:
        supported = values.get("SUPPORTED_LANGUAGES", [])
        if v not in supported:
            raise ValueError(f"Unsupported target language: {v}")
        return v

    @validator("TRANSCRIPTION_MODEL")
    def validate_transcription_model(cls, v: str) -> str:
        if v not in ["whisper-1", "gpt-4o-transcribe"]:
            raise ValueError(f"Invalid transcription model: {v}")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
