from bson import ObjectId
from datetime import datetime
import hashlib,imagehash
from PIL import Image
import json
import spacy
from spacy.cli import download
import tiktoken
from math import floor

import logging

logger = logging.getLogger(__name__)

try:
    nlp = spacy.load("en_core_web_sm")
except OSError as e:
    logger.exception("Failed to load spacy model: en_core_web_sm")
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

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
    import json

    @staticmethod
    def final_layout_extractor(props):
        layout = json.loads(props)
        result = ""
        for c in layout:
            component = list(c.keys())[0]
            data = c[component]["data"]
            value_key = list(data.keys())[0]
            if data[value_key].get("from") == "RESOLVE":
                text = ""
                for k, v in data[value_key].get("value", {}).items():
                    if k == "tableData":
                        for tdC in v:
                            for cC in tdC.get("children", []):
                                text += " " + cC.get("children", [{}])[0].get("text", "")
                    else:
                        text += " " + str(v)

                result += " " + text

        return result.strip()

    @staticmethod
    def splitter( text: str, max_tokens: int = 8000, overlap_tokens: int = None):
        try:
            if overlap_tokens is None:
                overlap_tokens = floor(max_tokens * 0.2)
            doc = nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            if not sentences:
                return []
            enc = tiktoken.encoding_for_model("gpt-4o")
            token_counts = [len(enc.encode(s)) for s in sentences]
            chunks = []
            start = 0
            while start < len(sentences):
                end = start
                token_acc = 0
                while end < len(sentences):
                    tok_count = token_counts[end]
                    if token_acc + tok_count <= max_tokens:
                        token_acc += tok_count
                        end += 1
                    else:
                        break
                if end == start:
                    sent = sentences[start]
                    chunks.append({
                        "search_content": sent,
                        "exact_content": sent
                    })
                    start += 1
                    continue
                overlap_count = 0
                overlap_acc = 0
                i = start - 1
                while i >= 0:
                    tok_count = token_counts[i]
                    if overlap_acc + tok_count <= overlap_tokens:
                        overlap_acc += tok_count
                        overlap_count += 1
                        i -= 1
                    else:
                        break
                if start == 0:
                    search_sents = sentences[start:end]
                    exact_sents = sentences[start:end]
                else:
                    search_sents = sentences[start - overlap_count:end]
                    exact_sents = sentences[start:end]
                chunks.append({
                    "search_content": " ".join(search_sents),
                    "exact_content": " ".join(exact_sents)
                })
                start = end
            return chunks
        except Exception as e:
            logger.exception(f"Error in Chunking Text in Splitter Class : {e}")
            raise RuntimeError(f"Error in Chunking Text in Splitter Class : {e}")