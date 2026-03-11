import subprocess
from pathlib import Path
import pandas as pd
from src.config import SUPPORTED_SPREADSHEETS

class CSVConvertor:
    @staticmethod
    def convert_to_csv(input_file: str, output_dir: str = None) -> Path:
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(input_path)

        if input_path.suffix.lower() not in SUPPORTED_SPREADSHEETS:
            raise ValueError(f"Unsupported format: {input_path.suffix}")

        output_dir = Path(output_dir) if output_dir else input_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        output_csv = output_dir / f"{input_path.stem}.csv"

        if input_path.suffix.lower() == ".csv":
            return input_path

        if input_path.suffix.lower() == ".xlsx":
            df = pd.read_excel(input_path)
            df.to_csv(output_csv, index=False)
            return output_csv

        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "csv",
                str(input_path),
                "--outdir", str(output_dir)
            ],
            check=True
        )

        return output_csv
