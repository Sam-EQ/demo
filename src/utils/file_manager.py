import uuid
from pathlib import Path

class FileManager:
    @staticmethod
    def create_temp_file(extension: str, base_dir: str = "data/temp_files") -> Path:
        if not extension.startswith("."):
            extension = f".{extension}"
        temp_dir = Path(base_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{extension}"
        file_path = temp_dir / filename
        file_path.touch()
        return file_path
    
    @staticmethod
    def remove_file(path: str | Path) -> bool:
        file_path = Path(path)

        if not file_path.exists():
            return False 
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        file_path.unlink()
        return True