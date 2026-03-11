import subprocess
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

class AudioConversion():
    @staticmethod
    def normalize_audio(
        input_path: str,
        output_path: str,
        sample_rate: int = 16000
    ):
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            if not input_path.exists():
                raise FileNotFoundError(input_path)

            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(input_path),
                "-ac", "1",
                "-ar", str(sample_rate),
                "-sample_fmt", "s16",
                "-vn",
                str(output_path)
            ]

            subprocess.run(cmd, check=True) 
        except Exception as e:
            logger.exception("Error in Converting {input_path} to {output_path}")
            raise RuntimeError("Error in Converting {input_path} to {output_path}")