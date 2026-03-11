import subprocess
from pathlib import Path
from src.config import PPTX_SUPPORTED

import logging

logger = logging.getLogger(__name__)


class PPTXConvertor:
    @staticmethod
    def convert_to_pptx(input_file: str, output_pptx_file: str) -> Path:
        input_path = Path(input_file)
        output_pptx = Path(output_pptx_file)

        if not input_path.exists():
            raise FileNotFoundError(input_path)

        suffix = input_path.suffix.lower()
        if suffix not in PPTX_SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}")

        if suffix == ".pptx":
            return input_path

        output_dir = output_pptx.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "pptx",
                str(input_path),
                "--outdir", str(output_dir)
            ],
            check=True
        )

        generated_pptx = output_dir / f"{input_path.stem}.pptx"
        if generated_pptx != output_pptx:
            generated_pptx.rename(output_pptx)

        return output_pptx
