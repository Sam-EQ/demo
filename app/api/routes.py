"""FastAPI route handlers for audio transcription and translation."""
import os
import time
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from loguru import logger
from app.core.config import settings
from app.services.transcription_service import transcribe_full
from app.services.translation_service import translate_text
from app.models.schemas import TranscriptionResponse, TranscriptionMetadata


router = APIRouter()


@router.post("/transcribe-and-translate", response_model=TranscriptionResponse)
async def transcribe_and_translate(
    file: UploadFile = File(..., description="Audio file to transcribe and translate"),
    target_language: str = Query(None, description="Target language code for translation (optional, overrides TARGET_LANGUAGE env var)")
) -> TranscriptionResponse:
    """
    Endpoint to ingest audio file, transcribe it, detect language, and translate to target language.
    
    Supported file formats: wav, mp3, m4a
    Supported languages: en, da, fr, pt, zh-Hans
    
    Args:
        file: Uploaded audio file
        target_language: Optional target language code (defaults to TARGET_LANGUAGE env var)
        
    Returns:
        TranscriptionResponse with original transcript, detected language, translated transcript, and metadata
        
    Raises:
        HTTPException: For validation errors (400, 413, 415) or server errors (500)
    """
    start_time = time.time()
    tmp_path: str = None
    chunks_info = []
    
    try:
        # Validate target language
        final_target = target_language or settings.TARGET_LANGUAGE
        if final_target not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Target language '{final_target}' is not supported. Supported languages: {settings.SUPPORTED_LANGUAGES}"
            )
        
        # Validate file format
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in (".wav", ".mp3", ".m4a"):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file format '{suffix}'. Supported formats: .wav, .mp3, .m4a"
            )
        
        # Stream file to disk with size validation (prevents memory spike)
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        tmp_filename = f"upload_{int(time.time() * 1000000)}_{file.filename}"
        tmp_path = os.path.join(settings.TEMP_DIR, tmp_filename)
        
        file_size = 0
        size_exceeded = False
        try:
            async with aiofiles.open(tmp_path, "wb") as f:
                while True:
                    # Read in chunks to avoid loading entire file into memory
                    chunk = await file.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    
                    file_size += len(chunk)
                    
                    # Enforce size limit during streaming
                    if file_size > settings.MAX_FILE_SIZE_BYTES:
                        size_exceeded = True
                        break
                    
                    await f.write(chunk)
        except Exception as e:
            # Clean up partial file on any error during streaming
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            logger.error(f"Error during file streaming: {e}")
            raise HTTPException(status_code=500, detail="Error while receiving file upload")
        
        # Handle size limit exceeded
        if size_exceeded:
            # Clean up partial file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed {settings.MAX_FILE_SIZE_BYTES} bytes"
            )
        
        if file_size == 0:
            # Clean up empty file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        logger.info(f"Processing file: {file.filename} ({file_size} bytes), target_language={final_target}")
        
        logger.debug(f"Saved uploaded file to: {tmp_path}")
        
        # Step 1: Transcribe audio (offload to threadpool to prevent event loop blocking)
        original_transcript, detected_language, chunk_transcripts, audio_duration, chunk_paths = await run_in_threadpool(
            transcribe_full, tmp_path
        )
        
        # Store chunk paths for cleanup
        chunks_info = chunk_paths
        
        logger.info(f"Transcription complete: language={detected_language}, transcript_length={len(original_transcript)}")
        
        # Step 2: Translate transcript (offload to threadpool to prevent event loop blocking)
        translated_transcript = await run_in_threadpool(
            translate_text, original_transcript, final_target
        )
        logger.info(f"Translation complete: target={final_target}, translated_length={len(translated_transcript)}")
        
        # Step 3: Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Step 4: Build response
        metadata = TranscriptionMetadata(
            audio_duration_seconds=round(audio_duration, 2),
            chunk_count=len(chunk_transcripts),
            transcription_model=settings.TRANSCRIPTION_MODEL,
            translation_model=settings.TRANSLATION_MODEL,
            processing_time_ms=processing_time_ms
        )
        
        response = TranscriptionResponse(
            original_transcript=original_transcript,
            detected_language=detected_language,
            translated_transcript=translated_transcript,
            metadata=metadata
        )
        
        logger.info(f"Request completed successfully in {processing_time_ms}ms")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(status_code=404, detail=f"File not found: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during processing")
    finally:
        # Cleanup temporary files
        cleanup_files = []
        
        # Add uploaded file
        if tmp_path and os.path.exists(tmp_path):
            cleanup_files.append(tmp_path)
        
        # Add chunk files
        if chunks_info:
            cleanup_files.extend(chunks_info)
        
        for file_path in cleanup_files:
            try:
                os.remove(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not remove temporary file {file_path}: {e}")
