import asyncio
import json
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/talent_toolkit/")

from src.config import EMPLOYEE_HANDBOOK
from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.process.chunk_processing.format.benefits import benefits
from src.cache.chunk_embedding import LMDBEmbeddingCache
from src.llm.openai_client import OpenAIClient
from src.utils.utils import Utils


class Policies():
    def __init__(self):
        self.mongo_data = MongoData()
        self.mongo_default = MongoDefault()
        self.embedding_cache = LMDBEmbeddingCache()
        self.openai_client = OpenAIClient()

    async def process(self):
        policies_data = await self.mongo_data.get_all_active_data(str(EMPLOYEE_HANDBOOK))
        results = []
        for b_data in policies_data:

            _id = b_data.get("_id", "")
            layouts = b_data.get("layouts",{})
            layout = b_data.get("layout","")
            final_layout = b_data.get("finalLayout","")
            values = b_data.get("values","")
            icon = b_data.get("icon","")
            path = b_data.get("path","")
            name = b_data.get("name","")
            sortOrder = b_data.get("sortOrder","")
            policyId = b_data.get("policyId","")
            parentId = b_data.get("parentId","")
            regions = b_data.get("regions",[]) # add join like usa, uk, india
            countries = b_data.get("countries",[]) # same as region
            locations = b_data.get("locations",[]) # all data are empty
            companyIds = b_data.get("companyIds",[]) 
            # ============ company ============
            company_data = ""
            for index,c_id in enumerate(companyIds):
                temp_c_data = await self._process_company(c_id)
                company_data+= f'Company {index+1} :\n Name of the Company : {temp_c_data["name"]}\nShort code for the company : {temp_c_data["shortName"]}'
            # ==========
            allUsers = b_data.get("allUsers","") # bool not needed
            userIds = b_data.get("userIds",[]) 
            # ============ user process ============
            user_data = []
            for d_user in user_data:
                val = await self.mongo_default.get_user_details(str(d_user))
                update_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
                update_id_email = val["email"]
            # =========== 
            acceptanceForm = b_data.get("acceptanceForm","")
            department = b_data.get("department","")
            restrictBy = b_data.get("restrictBy","")
            leadershipTitle = b_data.get("leadershipTitle","")
            jobTitle = b_data.get("jobTitle","")
            status = b_data.get("status","")
            createdAt = b_data.get("createdAt","")
            updatedAt = b_data.get("updatedAt","")

            creatorId = b_data.get("creatorId","")
            val = await self.mongo_default.get_user_details(creatorId)
            creator_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
            creator_id_email = val["email"]

            updatedById = b_data.get("updatedById","")
            val = await self.mongo_default.get_user_details(updatedById)
            update_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
            update_id_email = val["email"]

            


            
        
            
            # try:
            #     key = Hashing.text_hash(formatted_benefits)
            # except Exception as e:
            #     logger.info(f"Error in hashing the text {e}")
            #     raise RuntimeError(f"Error in hashing the text {e}")
            # cached = self.cache.get(key)
            # if self.reuse and cached:
            #     embeddings = cached
            #     logger.info("Taken chunk from the Cache")
            # else:
            #     embeddings = await self.openai_client.get_embedding(formatted_benefits)
            #     self.cache.set(key, embeddings)
            # results.append( { "id": str(b_data['_id']), 
            #         "text": formatted_benefits, 
            #         "search_content" : formatted_benefits,
            #         "exact_content" : formatted_benefits,
            #         "metadata":b_data, 
            #         "vector_field": embeddings} )
        return results
            
if __name__ == "__main__":
    obj = Policies()
    asyncio.run(obj.process())