import asyncio
import json
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/talent_toolkit/")

from src.config import JOB_DESCRIPTION
from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.process.chunk_processing.format.benefits import benefits
from src.cache.chunk_embedding import LMDBEmbeddingCache
from src.utils.utils import Utils
from src.llm.openai_client import OpenAIClient

class JobDescription():
    def __init__(self,reuse = True):
        self.mongo_data = MongoData()
        self.mongo_default = MongoDefault()
        self.embedding_cache = LMDBEmbeddingCache()
        self.openai_client = OpenAIClient()
        self.reuse = reuse
        
    async def process(self):
        benefits_data = await self.mongo_data.get_all_active_data(str(JOB_DESCRIPTION))
        print(benefits_data[0])
        results = []
        for b_data in benefits_data:
            id = str(b_data["_id"])
            jobCategory = b_data["jobCategory"]
            jobTitle = b_data["jobTitle"]
            responsibilities = b_data["responsibilities"]
            responsibilityText = b_data["responsibilityText"]
            officialTitle = b_data["officialTitle"]
            expYears = b_data["expYears"]
            proficiency = b_data["proficiency"]
            # inprogress = b_data["inprogress"]
            inprogressText = b_data["inprogressText"]
            # disclaimers = b_data["disclaimers"]
            disclaimersText = b_data["disclaimersText"]
            softwareproficiency = b_data["softwareproficiency"]
            isPrimary = b_data["isPrimary"]
            linkedDescriptions = b_data["linkedDescriptions"]
            creatorId = b_data["creatorId"]
            updatedById = b_data["updatedById"]
            createdAt = b_data["createdAt"]
            updatedAt = b_data["updatedAt"]

        #     title = b_data["title"]
        #     benefits_resource_type = b_data["benefitsResourceType"]
        #     status = b_data["status"]
        #     creatorId = b_data["creatorId"]
        #     val = await self.mongo_default.get_user_details(creatorId)
        #     creator_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
        #     creator_id_email = val["email"]
        #     updatedById = b_data["updatedById"]
        #     val = await self.mongo_default.get_user_details(updatedById)
        #     update_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
        #     update_id_email = val["email"]
        #     createdAt = b_data["createdAt"]
        #     updatedAt = b_data["updatedAt"]
        #     description = b_data["description"]
        #     appliesToCountries = ", ".join(b_data["appliesToCountries"])
        #     grouping = b_data["grouping"]
        #     del b_data["isDeleted"]
        #     benefilts_toolkit_article_json = ("```json\n" + json.dumps(b_data,indent=4,default=str)+ "\n```")
        #     formatted_benefits = benefits.format(
        #         benefilts_toolkit_article_json = benefilts_toolkit_article_json,
        #         title=title,
        #         benefits_resource_type = benefits_resource_type,
        #         status = status,
        #         creator_id_role = creator_id_role,
        #         creator_id_email = creator_id_email,
        #         update_id_role = update_id_role,
        #         update_id_email = update_id_email,
        #         createdAt = createdAt,
        #         updatedAt = updatedAt,
        #         description = description,
        #         appliesToCountries = appliesToCountries,
        #         grouping = grouping,
        #         formatted_benefits = formatted_benefits)
        #     try:
        #         key = Hashing.text_hash(formatted_benefits)
        #     except Exception as e:
        #         logger.info(f"Error in hashing the text {e}")
        #         raise RuntimeError(f"Error in hashing the text {e}")
        #     cached = self.cache.get(key)
        #     if self.reuse and cached:
        #         embeddings = cached
        #         logger.info("Taken chunk from the Cache")
        #     else:
        #         embeddings = await self.openai_client.get_embedding(formatted_benefits)
        #         self.cache.set(key, embeddings)
        #     results.append( { "id": str(b_data['_id']), 
        #             "text": formatted_benefits, 
        #             "search_content" : formatted_benefits,
        #             "exact_content" : formatted_benefits,
        #             "metadata":b_data, 
        #             "vector_field": embeddings} )
        # return results
            
if __name__ == "__main__":
    obj = JobDescription()
    asyncio.run(obj.process())