"""API routes for transcription and translation."""
import os
import time
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from app.core.config import settings
from app.services.transcription_service import transcribe_full
from app.services.translation_service import translate_text
from app.models.schemas import TranscriptionResponse, TranscriptionMetadata


router = APIRouter()


@router.post("/transcribe-and-translate", response_model=TranscriptionResponse)
async def transcribe_and_translate(
    file: UploadFile = File(...),
    target_language: str = Query(None)
) -> TranscriptionResponse:
    """Upload audio, transcribe, and translate. Supports wav, mp3, m4a."""
    start_time = time.time()
    tmp_path = None
    chunks_info = []
    
    try:
        final_target = target_language or settings.TARGET_LANGUAGE
        if final_target not in settings.SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target language: {final_target}"
            )
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        
        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in (".wav", ".mp3", ".m4a"):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported format: {suffix}. Use .wav, .mp3, or .m4a"
            )
        
        # Stream to disk to avoid memory issues with large files
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        tmp_filename = f"upload_{int(time.time() * 1000000)}_{file.filename}"
        tmp_path = os.path.join(settings.TEMP_DIR, tmp_filename)
        
        file_size = 0
        size_exceeded = False
        try:
            async with aiofiles.open(tmp_path, "wb") as f:
                while True:
                    chunk = await file.read(8192)
                    if not chunk:
                        break
                    
                    file_size += len(chunk)
                    if file_size > settings.MAX_FILE_SIZE_BYTES:
                        size_exceeded = True
                        break
                    
                    await f.write(chunk)
        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            logger.error(f"File upload error: {e}")
            raise HTTPException(status_code=500, detail="Upload failed")
        
        if size_exceeded:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {settings.MAX_FILE_SIZE_BYTES} bytes)"
            )
        
        if file_size == 0:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="Empty file")
        
        logger.info(f"Processing {file.filename} ({file_size} bytes) -> {final_target}")
        
        # Transcribe (blocking, so use threadpool)
        original_transcript, detected_language, chunk_transcripts, audio_duration, chunk_paths = await run_in_threadpool(
            transcribe_full, tmp_path
        )
        chunks_info = chunk_paths
        
        # Translate (also blocking)
        translated_transcript = await run_in_threadpool(
            translate_text, original_transcript, final_target
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        metadata = TranscriptionMetadata(
            audio_duration_seconds=round(audio_duration, 2),
            chunk_count=len(chunk_transcripts),
            transcription_model=settings.TRANSCRIPTION_MODEL,
            translation_model=settings.TRANSLATION_MODEL,
            processing_time_ms=processing_time_ms
        )
        
        return TranscriptionResponse(
            original_transcript=original_transcript,
            detected_language=detected_language,
            translated_transcript=translated_transcript,
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"File missing: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        # Cleanup temp files
        cleanup_files = []
        if tmp_path and os.path.exists(tmp_path):
            cleanup_files.append(tmp_path)
        if chunks_info:
            cleanup_files.extend(chunks_info)
        
        for path in cleanup_files:
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Cleanup failed for {path}: {e}")
