"""Pydantic schemas for API request/response models."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any


class ChunkTranscript(BaseModel):
    """Transcript information for a single audio chunk."""
    
    text: str = Field(..., description="Transcript text for this chunk")
    start_time: float = Field(..., description="Chunk start time in seconds")
    end_time: float = Field(..., description="Chunk end time in seconds")


class TranscriptionMetadata(BaseModel):
    """Metadata about the transcription and translation process."""
    
    audio_duration_seconds: float = Field(..., description="Total duration of the audio file in seconds")
    chunk_count: int = Field(..., description="Number of audio chunks processed")
    transcription_model: str = Field(..., description="OpenAI model used for transcription")
    translation_model: str = Field(..., description="OpenAI model used for translation")
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds")


class TranscriptionResponse(BaseModel):
    """Response model for transcription and translation endpoint."""
    
    original_transcript: str = Field(..., description="Original transcript text in detected language")
    detected_language: str = Field(..., description="Detected language code (normalized)")
    translated_transcript: str = Field(..., description="Translated transcript text in target language")
    metadata: TranscriptionMetadata = Field(..., description="Additional metadata about processing")
