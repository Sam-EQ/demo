"""Translation via OpenAI chat models."""
from typing import Optional
from openai import OpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.core.config import settings


_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


TRANSLATION_PROMPT = """You are a translation engine.
Translate the following text into the target language, preserving meaning, tone, formatting, and named entities.
Produce *only* the translated text. No commentary, explanations, or footnotes.

Target language: {target_language}

Text to translate:
\"\"\"
{text}
\"\"\"
"""


@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def translate_text(text: str, target_language: str) -> str:
    """Translate text to target language."""
    if target_language not in settings.SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported target language: {target_language}")
    
    language_names = {
        "en": "English",
        "da": "Danish",
        "fr": "French",
        "pt": "Portuguese",
        "zh-Hans": "Mandarin Chinese (Simplified)"
    }
    target_name = language_names.get(target_language, target_language)
    
    prompt = TRANSLATION_PROMPT.format(text=text, target_language=target_name)
    
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=settings.TRANSLATION_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional translation engine. Translate accurately and preserve all formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        # Validate response structure
        if not response or not hasattr(response, 'choices') or not response.choices:
            raise RuntimeError("Invalid API response structure")
        
        first_choice = response.choices[0]
        if not hasattr(first_choice, 'message') or not first_choice.message:
            raise RuntimeError("Missing message in response")
        
        content = first_choice.message.content
        if not content:
            raise RuntimeError("Empty translation response")
        
        translated = content.strip()
        if not translated:
            raise RuntimeError("Translation result is empty")
        
        return translated
        
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise
    except AttributeError as e:
        logger.error(f"Unexpected response format: {e}")
        raise RuntimeError(f"Translation failed - bad response format: {e}")
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise RuntimeError(f"Translation failed: {e}")
