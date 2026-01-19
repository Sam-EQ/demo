"""Translation service using OpenAI chat models."""
import time
from typing import Optional
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.core.config import settings


# Initialize OpenAI client
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


TRANSLATION_PROMPT_TEMPLATE = """You are a translation engine.
Translate the following text into the target language, preserving meaning, tone, formatting, and named entities.
Produce *only* the translated text. No commentary, explanations, or footnotes.

Target language: {target_language}

Text to translate:
\"\"\"
{text}
\"\"\"
"""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def translate_text(text: str, target_language: str) -> str:
    """
    Translate text to target language using OpenAI chat model.
    
    Args:
        text: Text to translate
        target_language: Target language code (e.g., "en", "fr", "zh-Hans")
        
    Returns:
        Translated text
        
    Raises:
        OpenAIError: If translation API call fails
        ValueError: If target language is not supported
    """
    if target_language not in settings.SUPPORTED_LANGUAGES:
        raise ValueError(f"Target language '{target_language}' is not supported. Supported: {settings.SUPPORTED_LANGUAGES}")
    
    logger.debug(f"Translating text to {target_language} (length: {len(text)} chars)")
    
    # Map language codes to readable names for the prompt
    language_names = {
        "en": "English",
        "da": "Danish",
        "fr": "French",
        "pt": "Portuguese",
        "zh-Hans": "Mandarin Chinese (Simplified)"
    }
    target_language_name = language_names.get(target_language, target_language)
    
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(
        text=text,
        target_language=target_language_name
    )
    
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=settings.TRANSLATION_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional translation engine. Translate accurately and preserve all formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent translations
            max_tokens=4000  # Reasonable limit for translations
        )
        
        translated_text = response.choices[0].message.content.strip()
        logger.debug(f"Translation completed (output length: {len(translated_text)} chars)")
        return translated_text
        
    except OpenAIError as e:
        logger.error(f"OpenAI translation API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during translation: {e}")
        raise RuntimeError(f"Translation failed: {e}")
