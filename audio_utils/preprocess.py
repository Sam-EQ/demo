import subprocess
import os
import tempfile
import logging
import glob

logger = logging.getLogger(__name__)

def process_and_segment(file_bytes: bytes, extension: str, segment_minutes: float = 1.0):
    """
    1. Converts input to Mono, 16kHz, 64kbps MP3.
    2. Segments into 1-minute chunks (~480KB each).
       At 64kbps, 1 minute is safely under the 22MB limit.
    """
    # Create temp file for the raw upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_input:
        temp_input.write(file_bytes)
        temp_input_path = temp_input.name

    base_path = temp_input_path + "_processed"
    full_audio_path = base_path + ".mp3"

    # Step 1: Normalize (Mono, 16kHz, 64kbps)
    conv_cmd = [
        "ffmpeg", "-y", "-i", temp_input_path,
        "-vn", "-acodec", "libmp3lame", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        full_audio_path
    ]

    try:
        logger.info("Normalizing audio to Mono 16kHz...")
        subprocess.run(conv_cmd, check=True, capture_output=True)
        
        # Step 2: Segment into 1-minute parts (60 seconds)
        # Using '-c copy' ensures no audio loss during splitting
        output_pattern = base_path + "_%03d.mp3"
        segment_seconds = int(segment_minutes * 60)
        
        split_cmd = [
            "ffmpeg", "-y", "-i", full_audio_path,
            "-f", "segment", "-segment_time", str(segment_seconds),
            "-c", "copy", output_pattern
        ]
        logger.info(f"Splitting into {segment_minutes} minute segments for live feel...")
        subprocess.run(split_cmd, check=True, capture_output=True)

        # Collect segment paths
        segments = sorted(glob.glob(f"{base_path}_[0-9][0-9][0-9].mp3"))
        return full_audio_path, segments

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg Error: {e.stderr.decode()}")
        raise RuntimeError("FFmpeg processing failed.")
    finally:
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)