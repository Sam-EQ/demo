from PIL import Image
from io import BytesIO
import base64
from pathlib import Path

def image_to_base64(image_path):
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not image_path.is_file():
        raise ValueError(f"Not a file: {image_path}")

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")