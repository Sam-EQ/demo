import subprocess
import uuid
import os


def preprocess_audio(input_path: str) -> str:
    """
    - Trim silence
    - Convert to mono
    - Resample to 16kHz
    Returns processed WAV path
    """

    output_path = f"/tmp/processed_{uuid.uuid4().hex}.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-af",
        "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:"
        "stop_periods=1:stop_silence=0.5:stop_threshold=-50dB",
        "-ac", "1",
        "-ar", "16000",
        output_path
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

    if not os.path.exists(output_path):
        raise RuntimeError("FFmpeg preprocessing failed")

    return output_path
