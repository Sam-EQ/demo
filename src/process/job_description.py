import asyncio
import json
import logging
from bs4 import BeautifulSoup

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
            id = str(b_data.get("_id")) if b_data.get("_id") else None
            # jobCategory = b_data.get("jobCategory", "") # old schema result
            jobTitle = b_data.get("jobTitle", "")
            responsibilities = b_data.get("responsibilities","")
            responsibilityText = b_data.get("responsibilityText","")
            # officialTitle = b_data.get("officialTitle","") # old schema result
            # expYears = b_data.get("expYears",{})  # old schema result
            # ======= year extarct
            # if expYears:
            #     min_year = expYears.get("min",0)
            #     max_year = expYears.get("max",0)
            # =======
            # proficiency = b_data.get("proficiency",[]) # old schema
            # proficiency_text = ", ".join(proficiency) 
            # ========
            # inprogressText = b_data.get("inprogressText","") # old schema
            # disclaimersText = b_data.get("disclaimersText","") # old schema
            # softwareproficiency = b_data.get("softwareproficiency",[]) # old schema
            # softwareproficiency_text = "" 
            # for soft_index, soft_pro in enumerate(softwareproficiency):
            #     softwareproficiency_text+= f"\n{soft_index}.) software - {soft_pro.get("software")}, proficiency - {soft_pro.get("proficiency")}"

            # isPrimary = b_data.get("isPrimary", "Not Provided")   # old schema
            # linkedDescriptions = b_data.get("linkedDescriptions")  # old schema
            # ========= link description ========
            # ========= creator id =============
            creatorId = b_data.get("creator")
            val = await self.mongo_default.get_user_details(creatorId)
            creator_id_role = ""
            creator_id_email = ""
            if val:
                creator_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
                creator_id_email = val["email"]
            # ======= updator id ============
            updatedById = b_data.get("updatedBy")
            val = await self.mongo_default.get_user_details(updatedById)
            update_id_role = ""
            update_id_email = ""
            if val:
                update_id_role = val["name"]["first"] +" "+ val["name"]["middle"] +" "+ val["name"]["last"]
                update_id_email = val["email"]

            
            createdAt = b_data.get("createdAt")
            updatedAt = b_data.get("updatedAt")

            draft = b_data.get("draft")
            # ========== dreaft
            draft_status = draft.get("status","")

            draft_responsibilities = draft.get("responsibilities", "")
            soup = BeautifulSoup(draft_responsibilities, "html.parser")
            soup_draft_responsibilities = soup.get_text(separator="\n", strip=True)

            draft_description = draft.get("description","")
            soup = BeautifulSoup(draft_description, "html.parser")
            soup_draft_descriptions = soup.get_text(separator="\n", strip=True)

            draft_proficiencies = draft.get("proficiencies", "")
            soup = BeautifulSoup(draft_proficiencies, "html.parser")
            soup_draft_proficiencies = soup.get_text(separator="\n", strip=True)

            draft_software = draft.get("software", "")
            soup = BeautifulSoup(draft_software, "html.parser")
            soup_draft_proficiencies = soup.get_text(separator="\n", strip=True)

            draft_certEduc = draft.get("certEduc", "")
            soup = BeautifulSoup(draft_certEduc, "html.parser")
            soup_draft_certEduc = soup.get_text(separator="\n", strip=True)
            # =========
            shortName = b_data.get("shortName","")
            level = b_data.get("level",0)
            department = b_data.get("department","")
            exemptStatus = b_data.get("exemptStatus","")
            descriptionType = b_data.get("descriptionType","")
            appliesToCountries = b_data.get("appliesToCountries",[])
            appliesToCountries_text = ""
            for atc_index, applt_to_con in enumerate(appliesToCountries):
                appliesToCountries_text += f"{atc_index}.) {applt_to_con}\n"    
            appliesToLocations = b_data.get("appliesToLocations",[])
            appliesToLocations_text = ""
            for atl_index, applt_to_loc in enumerate(appliesToCountries):
                appliesToLocations_text += f"{atl_index}.) {applt_to_loc}\n"
            appliesToCompanies = b_data.get("appliesToCompanies",[]) # omitted
            appliesToStudios = b_data.get("appliesToStudios",[]) # omitted
            # allowAccessIds = b_data.get("allowAccessIds") # list of user id what to add ? no need keep in metadata
            sustReqd = b_data.get("sustReqd","")  # what is the use ?
            licenseReqd = b_data.get("licenseReqd","") # what is the use ?
            reportsTo = b_data.get("reportsTo","") # no user if repointing to the same job description collection
            nextLevelUpTitles = b_data.get("nextLevelUpTitles",[]) # what is the use ?
            professionalorSupport = b_data.get("professionalorSupport","") # what is the use ?
            typicalUtilization = b_data.get("typicalUtilization",0) # what is the use ?  
            jobClusterForStaffing = b_data.get("jobClusterForStaffing") # what is the use ? everything is null
            description = b_data.get("description","")  
            descriptionText = b_data.get("descriptionText",) # no data found, if it is found it will be taged one?
            yrsOfExperience = b_data.get("yrsOfExperience","")  

            proficiencies = b_data.get("proficiencies", "") #  
            soup = BeautifulSoup(proficiencies, "html.parser")
            soup_proficiencies_s_text = soup.get_text(separator="\n", strip=True)

            proficienciesText = b_data.get("proficienciesText") # why proficiency text field is there but everthing in this empty
            software = b_data.get("software")
            softwareText = b_data.get("softwareText")
            certEduc = b_data.get("certEduc")
            certEducText = b_data.get("certEducText")
            additionalStarNotes = b_data.get("additionalStarNotes")
            additionalStarNotesText = b_data.get("additionalStarNotesText")
            status = b_data.get("status")
            dateAsOf = b_data.get("dateAsOf")
            CheckOutStatus = b_data.get("CheckOutStatus")
            





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