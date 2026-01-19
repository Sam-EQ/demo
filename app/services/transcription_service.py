"""OpenAI Whisper transcription."""
import os
import time
from typing import List, Tuple, Optional
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.core.config import settings
from app.services.audio_preprocessor import preprocess_audio
from app.models.schemas import ChunkTranscript


_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def normalize_language_code(code: str) -> str:
    """Whisper returns 'zh' sometimes, normalize to 'zh-Hans'."""
    if code.lower().startswith("zh"):
        return "zh-Hans"
    return code.lower()


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def transcribe_chunk(chunk_path: str) -> Tuple[str, str]:
    """Transcribe one chunk, return (text, language_code)."""
    if not os.path.exists(chunk_path):
        raise FileNotFoundError(f"Chunk missing: {chunk_path}")
    
    try:
        client = get_openai_client()
        with open(chunk_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=settings.TRANSCRIPTION_MODEL,
                file=audio_file,
                response_format="verbose_json"
            )
        
        text = response.text.strip() if hasattr(response, 'text') and response.text else ""
        
        # Language might be missing, handle gracefully
        detected_lang = None
        if hasattr(response, 'language') and response.language:
            detected_lang = response.language
        elif hasattr(response, 'language_code') and response.language_code:
            detected_lang = response.language_code
        
        if detected_lang is None and text:
            logger.warning(f"No language for chunk {chunk_path}, will use first valid")
        
        return text, detected_lang
        
    except OpenAIError as e:
        logger.error(f"OpenAI error transcribing {chunk_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Transcription failed for {chunk_path}: {e}")
        raise RuntimeError(f"Chunk transcription error: {e}")


def transcribe_full(input_path: str) -> Tuple[str, str, List[ChunkTranscript], float, List[str]]:
    """Process audio and transcribe all chunks. Returns transcript, language, chunks, duration, paths."""
    start_time = time.time()
    
    chunks_info, duration = preprocess_audio(input_path)
    logger.info(f"Preprocessed: {len(chunks_info)} chunks, {duration:.2f}s")
    
    chunk_transcripts = []
    detected_language = None
    chunk_paths = []
    
    for chunk_idx, (chunk_path, chunk_start, chunk_end) in enumerate(chunks_info):
        chunk_paths.append(chunk_path)
        try:
            text, lang = transcribe_chunk(chunk_path)
            
            # Use first chunk with actual text for language detection
            if detected_language is None and text and text.strip():
                if lang:
                    detected_language = lang
                    logger.info(f"Language from chunk {chunk_idx}: {lang}")
            
            chunk_transcripts.append(ChunkTranscript(
                text=text,
                start_time=chunk_start,
                end_time=chunk_end
            ))
            
        except Exception as e:
            logger.error(f"Chunk {chunk_idx} failed: {e}")
            # Cleanup remaining chunks on failure
            for remaining_path, _, _ in chunks_info[chunk_idx:]:
                try:
                    if os.path.exists(remaining_path):
                        os.remove(remaining_path)
                except Exception:
                    pass
            raise
    
    if detected_language is None:
        raise RuntimeError("No language detected from any chunk")
    
    normalized_lang = normalize_language_code(detected_language)
    
    if normalized_lang not in settings.SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {normalized_lang}. Supported: {settings.SUPPORTED_LANGUAGES}")
    
    # Join all chunks
    full_transcript = " ".join(ct.text for ct in chunk_transcripts)
    full_transcript = " ".join(full_transcript.split())  # normalize whitespace
    
    elapsed = time.time() - start_time
    logger.info(f"Transcription done: {elapsed:.2f}s, {len(full_transcript)} chars, {len(chunk_transcripts)} chunks")
    
    return full_transcript, normalized_lang, chunk_transcripts, duration, chunk_paths
