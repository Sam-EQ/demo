import logging
from typing import List, Union, Optional
from openai import AsyncOpenAI
from src.config import OPENAI_API_KEY
import threading


logger = logging.getLogger(__name__)

import threading
import logging
from openai import AsyncOpenAI
from src.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


class OpenAIClient:
 
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)

                    if not OPENAI_API_KEY:
                        logger.error("OPENAI_API_KEY is missing in src.config.")
                        raise ValueError("OPENAI_API_KEY must be configured.")

                    try:
                        instance._client = AsyncOpenAI(
                            api_key=OPENAI_API_KEY
                        )
                        logger.info("OpenAI Singleton Client initialized.")
                    except Exception as e:
                        logger.exception("Failed to initialize OpenAI client")
                        raise ConnectionError(
                            f"OpenAI connection failure: {e}"
                        )

                    cls._instance = instance

        return cls._instance


    async def get_embeddings(
        self, 
        input_data: Union[str, List[str]], 
        model: str = "text-embedding-3-large"
    ) -> Union[List[float], List[List[float]]]:
        """
        Smart Hybrid Method:
        - If input is a string: Returns a single list of floats.
        - If input is a list: Returns a list of lists of floats.
        """
        if not input_data:
            return []

        # Determine if we are dealing with a single string or a batch
        is_single = isinstance(input_data, str)
        
        # Pre-process: Clean newlines and wrap single string in a list for the API
        if is_single:
            texts = [input_data.replace("\n", " ").strip()]
        else:
            texts = [t.replace("\n", " ").strip() for t in input_data if t]

        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                input=texts,
                model=model
            )
            
            # Return single vector for single input, or batch for list input
            if is_single:
                return response.data[0].embedding
            return [item.embedding for item in response.data]

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise RuntimeError(f"OpenAI Embedding Error: {e}")

    async def get_description(self, image_base64: str, model: str = "gpt-4o") -> str:
 
        if not image_base64:
            logger.error("get_description called with empty image data.")
            raise ValueError("image_base64 data is required.")

        system_prompt = (
            "You describe images in one short, crisp sentence for accessibility and search."
        )

        user_prompt = (
            "Describe this image in one short sentence (under 25 words). "
            "Focus on what the image shows: e.g. diagram, screenshot, chart, photo, or key elements."
        )

        try:
            response = await self._client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=80,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            },
                        ],
                    },
                ],
            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Vision model returned empty output.")

            return content

        except Exception as e:
            logger.error(f"Image description failed: {e}")
            raise RuntimeError(f"OpenAI Vision Error: {e}")

    async def refine_markdown(
        self, markdown: str, model: str = "gpt-4o", max_tokens: int = 16000
    ) -> str:
        """Refine markdown: add headings, remove repeated logos/logo-only pages, remove OCR duplicate text, neat tables. Returns refined markdown only."""
        if not markdown or not markdown.strip():
            return markdown
        system_prompt = (
            "You refine markdown documents. Apply these rules and return ONLY the refined markdown (no commentary or wrapper):\n"
            "- Add or improve clear, hierarchical headings where they help structure.\n"
            "- Remove repeated logos and pages that contain only logos or decorative branding.\n"
            "- Remove any OCR text that merely duplicates content already described in image captions or that is redundant.\n"
            "- Format tables neatly (consistent alignment, clear headers).\n"
            "- Keep all substantive content, image references, and image descriptions. Preserve markdown links and image syntax."
        )
        try:
            response = await self._client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": markdown},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            return content if content else markdown
        except Exception as e:
            logger.error(f"Refine markdown failed: {e}")
            raise RuntimeError(f"OpenAI Refine Error: {e}")