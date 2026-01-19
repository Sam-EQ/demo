"""Transcription service using OpenAI Whisper API."""
import os
import time
from typing import List, Tuple, Optional
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.core.config import settings
from app.services.audio_preprocessor import preprocess_audio
from app.models.schemas import ChunkTranscript


# Initialize OpenAI client
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def normalize_language_code(code: str) -> str:
    """
    Normalize language codes from Whisper to internal standard.
    
    Whisper may return "zh" for Chinese, which we normalize to "zh-Hans".
    
    Args:
        code: Language code from Whisper API
        
    Returns:
        Normalized language code
    """
    if code.lower().startswith("zh"):
        return "zh-Hans"
    return code.lower()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def transcribe_chunk(chunk_path: str) -> Tuple[str, str]:
    """
    Transcribe a single audio chunk using OpenAI Whisper API.
    
    Args:
        chunk_path: Path to audio chunk file
        
    Returns:
        Tuple of (transcript_text, detected_language_code)
        
    Raises:
        OpenAIError: If transcription API call fails
        FileNotFoundError: If chunk file doesn't exist
    """
    if not os.path.exists(chunk_path):
        raise FileNotFoundError(f"Chunk file not found: {chunk_path}")
    
    logger.debug(f"Transcribing chunk: {chunk_path}")
    
    try:
        client = get_openai_client()
        with open(chunk_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=settings.TRANSCRIPTION_MODEL,
                file=audio_file,
                response_format="verbose_json"  # Get language detection
            )
        
        # Extract text and language
        text = response.text.strip()
        detected_lang = response.language if hasattr(response, 'language') else None
        
        if detected_lang is None:
            logger.warning(f"No language detected for chunk {chunk_path}, defaulting to 'en'")
            detected_lang = "en"
        
        logger.debug(f"Chunk transcribed: language={detected_lang}, text_length={len(text)}")
        return text, detected_lang
        
    except OpenAIError as e:
        logger.error(f"OpenAI transcription API error for chunk {chunk_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error transcribing chunk {chunk_path}: {e}")
        raise RuntimeError(f"Transcription failed for chunk: {e}")


def transcribe_full(input_path: str) -> Tuple[str, str, List[ChunkTranscript], float, List[str]]:
    """
    Preprocess audio and transcribe all chunks, then aggregate results.
    
    Args:
        input_path: Path to input audio file
        
    Returns:
        Tuple of:
        - full_transcript: Complete transcript text
        - detected_language: Normalized language code
        - chunk_transcripts: List of ChunkTranscript objects with timestamps
        - audio_duration_seconds: Total audio duration
        - chunk_paths: List of chunk file paths for cleanup
        
    Raises:
        ValueError: If detected language is not supported
        RuntimeError: If preprocessing or transcription fails
    """
    start_time = time.time()
    logger.info(f"Starting transcription for: {input_path}")
    
    # Step 1: Preprocess audio (normalize, trim, chunk)
    chunks_info, duration = preprocess_audio(input_path)
    logger.info(f"Audio preprocessed: {len(chunks_info)} chunks, duration={duration:.2f}s")
    
    # Step 2: Transcribe each chunk
    chunk_transcripts: List[ChunkTranscript] = []
    detected_language: Optional[str] = None
    chunk_paths: List[str] = []
    
    for chunk_idx, (chunk_path, chunk_start, chunk_end) in enumerate(chunks_info):
        chunk_paths.append(chunk_path)
        try:
            text, lang = transcribe_chunk(chunk_path)
            
            # Use first chunk's detected language
            if detected_language is None:
                detected_language = lang
                logger.info(f"Detected language from chunk 0: {lang}")
            
            chunk_transcripts.append(ChunkTranscript(
                text=text,
                start_time=chunk_start,
                end_time=chunk_end
            ))
            logger.debug(f"Chunk [{chunk_start:.2f}-{chunk_end:.2f}s]: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to transcribe chunk {chunk_idx}: {e}")
            # Clean up remaining chunks
            for remaining_chunk_path, _, _ in chunks_info[chunk_idx:]:
                try:
                    if os.path.exists(remaining_chunk_path):
                        os.remove(remaining_chunk_path)
                except Exception:
                    pass
            raise
    
    # Step 3: Normalize and validate language
    if detected_language is None:
        raise RuntimeError("Could not detect language from any chunk")
    
    normalized_lang = normalize_language_code(detected_language)
    logger.info(f"Normalized language code: {detected_language} -> {normalized_lang}")
    
    if normalized_lang not in settings.SUPPORTED_LANGUAGES:
        logger.error(f"Detected language '{normalized_lang}' not in supported list: {settings.SUPPORTED_LANGUAGES}")
        raise ValueError(f"Detected language '{normalized_lang}' is not supported. Supported languages: {settings.SUPPORTED_LANGUAGES}")
    
    # Step 4: Aggregate chunk transcripts
    # Join with spaces, preserving original text
    full_transcript = " ".join(ct.text for ct in chunk_transcripts)
    
    # Normalize punctuation (basic cleanup)
    # Remove extra spaces
    full_transcript = " ".join(full_transcript.split())
    
    processing_time = time.time() - start_time
    logger.info(f"Transcription completed in {processing_time:.2f}s: {len(full_transcript)} chars, {len(chunk_transcripts)} chunks")
    
    return full_transcript, normalized_lang, chunk_transcripts, duration, chunk_paths
