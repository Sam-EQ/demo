import subprocess
from pathlib import Path
from src.config import DOCX_SUPPORTED

class DocxConvertor:
    @staticmethod
    def convert_to_docx(input_file: str, output_dir: str = None) -> Path:
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(input_path)

        suffix = input_path.suffix.lower()

        if suffix not in DOCX_SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}")

        output_dir = Path(output_dir) if output_dir else input_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        output_docx = output_dir / f"{input_path.stem}.docx"

        if suffix == ".docx":
            return input_path

        if suffix == ".pages":
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to", "docx",
                    str(input_path),
                    "--outdir", str(output_dir)
                ],
                check=True
            )
            return output_docx
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "docx",
                str(input_path),
                "--outdir", str(output_dir)
            ],
            check=True
        )

        return output_docx
