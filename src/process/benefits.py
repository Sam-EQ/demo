import asyncio
import json
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/talent_toolkit/")

from src.config import BENEFITS,INDEX_NAME
from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.process.chunk_processing.format.benefits import benefits
from src.cache.chunk_embedding import LMDBEmbeddingCache
from src.llm.openai_client import OpenAIClient
from src.utils.utils import Utils

class Benefits():
    def __init__(self,reuse = True):
        self.mongo_data = MongoData()
        self.mongo_default = MongoDefault()
        self.embedding_cache = LMDBEmbeddingCache()
        self.openai_client = OpenAIClient()
        self.reuse = reuse

    async def _process_company(self,company_id):
        _id = await self.mongo_default.get_company_ids()
        return await self.mongo_data.get_data_from_db(str(_id),company_id)

    async def _process_studio(self,company_id):
        _id = await self.mongo_default.get_studio_ids()
        return await self.mongo_data.get_data_from_db(str(_id),company_id)
    
    async def process(self):
        benefits_data = await self.mongo_data.get_all_active_data(str(BENEFITS))
        results = []
        for b_data in benefits_data:
            title = b_data["title"]
            benefits_resource_type = b_data["benefitsResourceType"]
            appliesToCompanies = b_data["appliesToCompanies"]
            appliesToStudios = b_data["appliesToStudios"]
            status = b_data["status"]
            creatorId = b_data["creatorId"]
            val = await self.mongo_default.get_user_details(creatorId)
            creator_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
            creator_id_email = val["email"]
            updatedById = b_data["updatedById"]
            val = await self.mongo_default.get_user_details(updatedById)
            update_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
            update_id_email = val["email"]
            createdAt = b_data["createdAt"]
            updatedAt = b_data["updatedAt"]
            # ==============
            description = b_data.get("description","")
            uploadedBy = b_data.get("uploadedBy","")
            parentId = b_data.get("parentId","")
            talentToolkitType = b_data.get("talentToolkitType","")
            effectiveDate = b_data.get("effectiveDate","")
            fileArray = b_data.get("fileArray","")
            appliesToLocations = b_data.get("appliesToLocations",[])
            formType = b_data.get("formType","")
            # ===============
            appliesToCountries = ", ".join(b_data["appliesToCountries"])
            grouping = b_data["grouping"]
            del b_data["isDeleted"]
            benefilts_toolkit_article_json = ("```json\n" + json.dumps(b_data,indent=4,default=str)+ "\n```")
            # ============ company ================
            company_data = ""
            for index,c_id in enumerate(appliesToCompanies):
                temp_c_data = await self._process_company(c_id)
                company_data+= f'Company {index+1} :\n Name of the Company : {temp_c_data["name"]}\nShort code for the company : {temp_c_data["shortName"]}'
            # ============ studio ==============
            studio_data = ""
            for index,a_studio in enumerate(appliesToStudios):
                temp_a_data = await self._process_studio(a_studio)
                inflation_trends = ""
                for infla_index, infla in enumerate(temp_a_data["inflationArray"]):
                    inflation_trends += f'inflation persentage is {infla["percent"]} for the year {infla["year"]}'
                address = f'city : {infla["address"]["city"]} \ncountry : {infla["address"]["country"]}\nlatitude :{infla["address"]["lat"]}\n longitude : {infla["address"]["long"]}'
                studio_data+= f'Name : {a_studio["name"]}\nShort Name : {a_studio["shortName"]}\naddress : {address} \ninflation trend : {inflation_trends}'
            # ========== 
            additional_links_and_data = "" 
            for link_index, link_data in enumerate(b_data["linkArray"]):
                additional_links_and_data += f'link data {link_index} : {link_data["title"]}({link_data["url"]})'
            # =========
            sub_resource_type = b_data["subResourceType"]

            formatted_benefits = benefits.format(
                benefilts_toolkit_article_json = benefilts_toolkit_article_json,
                title=title,
                benefits_resource_type = benefits_resource_type,
                status = status,
                creator_id_role = creator_id_role,
                creator_id_email = creator_id_email,
                update_id_role = update_id_role,
                update_id_email = update_id_email,
                createdAt = createdAt,
                updatedAt = updatedAt,
                description = description,
                appliesToCountries = appliesToCountries,
                grouping = grouping,
                company_data = company_data,
                studio_data = studio_data,
                additional_links_and_data = additional_links_and_data,
                sub_resource_type = sub_resource_type )
            try:
                key = Utils.text_hash(formatted_benefits)
            except Exception as e:
                logger.info(f"Error in hashing the text {e}")
                raise RuntimeError(f"Error in hashing the text {e}")
            cached = self.embedding_cache.get(key)
            if self.reuse and cached:
                embeddings = cached
                logger.info("Taken chunk from the Cache")
            else:
                embeddings = await self.openai_client.get_embedding(formatted_benefits)
                self.embedding_cache.set(key, embeddings)
            results.append( { "id": str(b_data['_id']), 
                    "text": formatted_benefits, 
                    "search_content" : formatted_benefits,
                    "exact_content" : formatted_benefits,
                    "metadata":b_data, 
                    "vector_field": embeddings} )
        return results
            
if __name__ == "__main__":
    obj = Benefits()
    data = asyncio.run(obj._process_company("5faf2b97ed9da40013909b04",))
    print(data)