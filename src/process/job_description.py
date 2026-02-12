import asyncio
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

from src.config import JOB_DESCRIPTION
from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.cache.chunk_embedding import LMDBEmbeddingCache
from src.utils.utils import Utils
from src.llm.openai_client import OpenAIClient


class JobDescription:
    def __init__(self, reuse=True):
        self.mongo_data = MongoData()
        self.mongo_default = MongoDefault()
        self.embedding_cache = LMDBEmbeddingCache()
        self.openai_client = OpenAIClient()
        self.reuse = reuse

    def _clean_html(self, html_text):
        if not html_text:
            return ""
        soup = BeautifulSoup(html_text, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    async def _get_user_info(self, user_id):
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
        job_data = await self.mongo_data.get_all_active_data(str(JOB_DESCRIPTION))
        results = []

        for jd in job_data:
            try:
                jobTitle = jd.get("jobTitle", "")
                department = jd.get("department", "")
                level = jd.get("level", "")
                description = jd.get("description", "")
                yrsOfExperience = jd.get("yrsOfExperience", "")

                responsibilities_html = jd.get("responsibilities", "")
                proficiencies_html = jd.get("proficiencies", "")
                software_html = jd.get("software", "")
                certEduc_html = jd.get("certEduc", "")

                responsibilities = self._clean_html(responsibilities_html)
                proficiencies = self._clean_html(proficiencies_html)
                software = self._clean_html(software_html)
                certEduc = self._clean_html(certEduc_html)

                appliesToCountries = ", ".join(jd.get("appliesToCountries", []))

                creatorId = jd.get("creator")
                updatedById = jd.get("updatedBy")

                creator_name, creator_email = await self._get_user_info(creatorId)
                updater_name, updater_email = await self._get_user_info(updatedById)

                createdAt = jd.get("createdAt", "")
                updatedAt = jd.get("updatedAt", "")

                formatted_text = f"""
# Job Description

## Job Information
- **Title:** {jobTitle}
- **Department:** {department}
- **Level:** {level}
- **Years of Experience:** {yrsOfExperience}
- **Applies To Countries:** {appliesToCountries}

## Description
{description}

## Responsibilities
{responsibilities}

## Proficiencies
{proficiencies}

## Software Skills
{software}

## Certifications / Education
{certEduc}

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
                    "id": str(jd.get("_id")),
                    "text": formatted_text,
                    "search_content": formatted_text,
                    "exact_content": formatted_text,
                    "metadata": Utils.make_json_safe(jd),
                    "vector_field": embedding
                })

            except Exception as e:
                logger.exception(f"Error processing job description: {e}")

        return results


if __name__ == "__main__":
    obj = JobDescription()
    data = asyncio.run(obj.process())
    print(f"Processed {len(data)} job descriptions")
