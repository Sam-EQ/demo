"""
Adds vector embeddings to organized records (id, text, metadata) using OpenAI embeddings API.
"""
import logging
from typing import List, Dict, Any

from src.llm_models.openai_llms import OpenAIClient

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50


async def add_embeddings_to_records(
    records: List[Dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> List[Dict[str, Any]]:
    """
    Fills vector_field on each record by embedding record["text"].
    Uses OpenAIClient.get_embeddings in batches. Returns the same list (modified in place).
    """
    if not records:
        return records

    texts = [r.get("text", "") or "" for r in records]
    client = OpenAIClient()
    all_vectors = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vecs = await client.get_embeddings(batch)
        all_vectors.extend(vecs)
        logger.info("Embedded batch %d/%d", i // batch_size + 1, (len(texts) + batch_size - 1) // batch_size)

    for r, vec in zip(records, all_vectors):
        r["vector_field"] = vec

    return records