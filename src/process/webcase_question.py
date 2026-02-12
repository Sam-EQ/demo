import asyncio
import logging

logger = logging.getLogger(__name__)

from src.config import WEBCAST_QUESTION
from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.cache.chunk_embedding import LMDBEmbeddingCache
from src.llm.openai_client import OpenAIClient
from src.utils.utils import Utils


class WebcastQuestion:
    def __init__(self, reuse=True):
        self.mongo_data = MongoData()
        self.mongo_default = MongoDefault()
        self.embedding_cache = LMDBEmbeddingCache()
        self.openai_client = OpenAIClient()
        self.reuse = reuse

    async def _get_user_info(self, user_id):
        """Safely fetch user details"""
        try:
            user = await self.mongo_default.get_user_details(user_id)
            if not user:
                return "Unknown User", "Unknown Email"

            name_parts = [
                user.get("name", {}).get("first"),
                user.get("name", {}).get("middle"),
                user.get("name", {}).get("last"),
            ]
            full_name = " ".join([p for p in name_parts if p])
            email = user.get("email", "Unknown Email")

            return full_name, email

        except Exception as e:
            logger.warning(f"Error fetching user {user_id}: {e}")
            return "Unknown User", "Unknown Email"

    async def process(self):
        webcast_data = await self.mongo_data.get_all_active_data(str(WEBCAST_QUESTION))
        results = []

        for q_data in webcast_data:
            try:
                question = q_data.get("question", "")
                answer = q_data.get("answer", "")

                creatorId = q_data.get("creatorId")
                updatedById = q_data.get("updatedById")

                creator_name, creator_email = await self._get_user_info(creatorId)
                updater_name, updater_email = await self._get_user_info(updatedById)

                createdAt = q_data.get("createdAt", "")
                updatedAt = q_data.get("updatedAt", "")

                formatted_text = f"""
# Webcast Knowledge Base Entry

## Question
{question}

## Answer
{answer}

## Creator Information
- Name: {creator_name}
- Email: {creator_email}

## Last Updated By
- Name: {updater_name}
- Email: {updater_email}

## Timestamps
- Created At: {createdAt}
- Updated At: {updatedAt}
"""

                key = Utils.text_hash(formatted_text)

                cached_embedding = self.embedding_cache.get(key)

                if self.reuse and cached_embedding:
                    embedding = cached_embedding
                    logger.info("Using cached embedding")
                else:
                    embedding = await self.openai_client.get_embedding(formatted_text)
                    self.embedding_cache.set(key, embedding)
                    logger.info("Generated new embedding")

                results.append({
                    "id": str(q_data.get("_id")),
                    "text": formatted_text,
                    "search_content": formatted_text,
                    "exact_content": formatted_text,
                    "metadata": Utils.make_json_safe(q_data),
                    "vector_field": embedding
                })

            except Exception as e:
                logger.exception(f"Error processing webcast question: {e}")

        return results


if __name__ == "__main__":
    obj = WebcastQuestion()
    data = asyncio.run(obj.process())
    for d in data:
        print("\n" + "="*80)
        print(d["text"])

