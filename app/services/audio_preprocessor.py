"""FFmpeg-based audio preprocessing."""
import os
import subprocess
import uuid
from typing import List, Tuple
from loguru import logger
from app.core.config import settings


def get_audio_duration(path: str) -> float:
    """Get duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"Failed to get duration for {path}: {e}")
        raise RuntimeError(f"Could not get audio duration: {e}")


def run_ffmpeg(args: List[str]) -> None:
    """Run ffmpeg with given args. No shell=True for safety."""
    try:
        subprocess.run(
            ["ffmpeg", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else "Unknown error"
        logger.error(f"ffmpeg failed: {error_msg}")
        raise RuntimeError(f"ffmpeg error (code {e.returncode}): {error_msg}")


def normalize_audio(input_path: str, output_path: str) -> None:
    """Convert to mono, 16kHz."""
    args = [
        "-y",
        "-i", input_path,
        "-ac", "1",  # mono
        "-ar", "16000",  # 16kHz
        output_path
    ]
    run_ffmpeg(args)


def trim_silence(input_path: str, output_path: str) -> None:
    """Remove leading/trailing silence. Uses areverse trick to handle both ends."""
    # silenceremove twice with areverse to catch both start and end
    args = [
        "-y",
        "-i", input_path,
        "-af", "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:detection=peak,areverse,silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:detection=peak,areverse",
        output_path
    ]
    run_ffmpeg(args)


def chunk_audio(input_path: str, max_length: float) -> List[Tuple[str, float, float]]:
    """Split audio into max_length second chunks. Returns (path, start, end) tuples."""
    duration = get_audio_duration(input_path)
    num_chunks = int((duration + max_length - 1) // max_length) or 1
    
    chunks = []
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
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
            "-ac", "1",
            "-ar", "16000",
            chunk_path
        ]
        run_ffmpeg(args)
        chunks.append((chunk_path, start, end))
    
    return chunks


def preprocess_audio(input_path: str) -> Tuple[List[Tuple[str, float, float]], float]:
    """Full pipeline: normalize -> trim -> chunk. Returns chunks and duration."""
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    
    unique_id = uuid.uuid4().hex[:8]
    norm_path = os.path.join(settings.TEMP_DIR, f"normalized_{unique_id}.wav")
    trim_path = os.path.join(settings.TEMP_DIR, f"trimmed_{unique_id}.wav")
    
    try:
        normalize_audio(input_path, norm_path)
        trim_silence(norm_path, trim_path)
        
        duration = get_audio_duration(trim_path)
        if duration > settings.MAX_AUDIO_DURATION_SECONDS:
            raise ValueError(f"Audio too long: {duration}s > {settings.MAX_AUDIO_DURATION_SECONDS}s")
        
        chunks = chunk_audio(trim_path, settings.CHUNK_MAX_LENGTH_SECONDS)
        
        # Clean up intermediates
        for path in [norm_path, trim_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass  # best effort cleanup
        
        return chunks, duration
        
    except Exception:
        # Cleanup on any error
        for path in [norm_path, trim_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        raise
