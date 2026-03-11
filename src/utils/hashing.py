import hashlib,imagehash
from PIL import Image

class Hashing():
    @staticmethod
    def text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    @staticmethod
    def image_hash(image):
        return imagehash.phash(Image.open(image))