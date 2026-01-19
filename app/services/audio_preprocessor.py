"""Audio preprocessing service using FFmpeg for normalization, silence trimming, and chunking."""
import os
import subprocess
import uuid
import contextlib
from typing import List, Tuple
from loguru import logger
from app.core.config import settings


def get_audio_duration(path: str) -> float:
    """
    Get audio file duration in seconds using FFprobe.
    
    Args:
        path: Path to the audio file
        
    Returns:
        Duration in seconds
        
    Raises:
        RuntimeError: If FFprobe fails to read the file
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"Failed to get audio duration for {path}: {e}")
        raise RuntimeError(f"Could not determine audio duration: {e}")


def run_ffmpeg(args: List[str]) -> None:
    """
    Execute FFmpeg command safely without shell=True.
    
    Args:
        args: List of FFmpeg arguments
        
    Raises:
        RuntimeError: If FFmpeg execution fails
    """
    logger.debug(f"Running ffmpeg with args: {args}")
    try:
        result = subprocess.run(
            ["ffmpeg", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else "Unknown FFmpeg error"
        logger.error(f"FFmpeg error: {error_msg}")
        raise RuntimeError(f"FFmpeg failed with exit code {e.returncode}: {error_msg}")


def normalize_audio(input_path: str, output_path: str) -> None:
    """
    Normalize audio: convert to mono channel and 16kHz sample rate.
    
    Args:
        input_path: Path to input audio file
        output_path: Path to save normalized audio file
        
    Raises:
        RuntimeError: If FFmpeg normalization fails
    """
    logger.debug(f"Normalizing audio: {input_path} -> {output_path}")
    args = [
        "-y",  # Overwrite output file
        "-i", input_path,
        "-ac", "1",  # Mono channel
        "-ar", "16000",  # 16kHz sample rate
        output_path
    ]
    run_ffmpeg(args)


def trim_silence(input_path: str, output_path: str) -> None:
    """
    Trim leading and trailing silence from audio file.
    
    Args:
        input_path: Path to input audio file
        output_path: Path to save trimmed audio file
        
    Raises:
        RuntimeError: If FFmpeg silence removal fails
    """
    logger.debug(f"Trimming silence: {input_path} -> {output_path}")
    # Remove silence at start and end
    # silenceremove parameters:
    # - start_periods=1: detect one period of silence at start
    # - start_silence=0.5: minimum silence duration to detect (0.5 seconds)
    # - start_threshold=-50dB: silence threshold
    # - detection=peak: use peak detection
    # - areverse: reverse audio, then remove silence again (for trailing silence)
    args = [
        "-y",
        "-i", input_path,
        "-af", "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:detection=peak,areverse,silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:detection=peak,areverse",
        output_path
    ]
    run_ffmpeg(args)


def chunk_audio(input_path: str, max_length: float) -> List[Tuple[str, float, float]]:
    """
    Chunk audio into segments of maximum length.
    
    Args:
        input_path: Path to input audio file
        max_length: Maximum length of each chunk in seconds
        
    Returns:
        List of tuples: (chunk_path, start_time, end_time)
        
    Raises:
        RuntimeError: If chunking fails
    """
    duration = get_audio_duration(input_path)
    num_chunks = int((duration + max_length - 1) // max_length)  # Ceiling division
    
    if num_chunks == 0:
        num_chunks = 1
    
    chunks: List[Tuple[str, float, float]] = []
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    logger.debug(f"Chunking audio of duration {duration}s into {num_chunks} chunks")
    
    for i in range(num_chunks):
        start = i * max_length
        end = min((i + 1) * max_length, duration)
        chunk_filename = f"{base_name}_chunk_{i}_{uuid.uuid4().hex[:8]}.wav"
        chunk_path = os.path.join(settings.TEMP_DIR, chunk_filename)
        
        args = [
            "-y",
            "-i", input_path,
            "-ss", str(start),
            "-to", str(end),
            "-ac", "1",  # Mono
            "-ar", "16000",  # 16kHz
            chunk_path
        ]
        run_ffmpeg(args)
        chunks.append((chunk_path, start, end))
        logger.debug(f"Created chunk {i+1}/{num_chunks}: {chunk_path} ({start}s - {end}s)")
    
    return chunks


def preprocess_audio(input_path: str) -> Tuple[List[Tuple[str, float, float]], float]:
    """
    Full audio preprocessing pipeline: normalize, trim silence, and chunk.
    
    Args:
        input_path: Path to input audio file
        
    Returns:
        Tuple of (list of chunk tuples, total duration)
        Each chunk tuple is (chunk_path, start_time, end_time)
        
    Raises:
        ValueError: If audio duration exceeds maximum allowed
        RuntimeError: If preprocessing fails
    """
    # Ensure temp directory exists
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    
    # Generate unique filenames for intermediate files
    unique_id = uuid.uuid4().hex[:8]
    norm_path = os.path.join(settings.TEMP_DIR, f"normalized_{unique_id}.wav")
    trim_path = os.path.join(settings.TEMP_DIR, f"trimmed_{unique_id}.wav")
    
    try:
        # Step 1: Normalize audio
        normalize_audio(input_path, norm_path)
        
        # Step 2: Trim silence
        trim_silence(norm_path, trim_path)
        
        # Step 3: Validate duration
        duration = get_audio_duration(trim_path)
        if duration > settings.MAX_AUDIO_DURATION_SECONDS:
            logger.error(f"Audio duration {duration}s exceeds maximum allowed {settings.MAX_AUDIO_DURATION_SECONDS}s")
            raise ValueError(f"Audio duration {duration}s exceeds maximum allowed {settings.MAX_AUDIO_DURATION_SECONDS}s")
        
        # Step 4: Chunk audio
        chunks = chunk_audio(trim_path, settings.CHUNK_MAX_LENGTH_SECONDS)
        
        # Clean up intermediate files (normalized and trimmed)
        for path in [norm_path, trim_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.debug(f"Cleaned up intermediate file: {path}")
            except Exception as e:
                logger.warning(f"Could not remove intermediate file {path}: {e}")
        
        return chunks, duration
        
    except Exception as e:
        # Cleanup on error
        for path in [norm_path, trim_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        raise
