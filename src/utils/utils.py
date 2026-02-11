from bson import ObjectId
from datetime import datetime
import hashlib,imagehash
from PIL import Image

class Utils:
    @staticmethod
    def make_json_safe(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: Utils.make_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [Utils.make_json_safe(v) for v in obj]
        return obj
    
    @staticmethod
    def text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    @staticmethod
    def image_hash(image):
        return imagehash.phash(Image.open(image))
