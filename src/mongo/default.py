from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio

from src.config import MONGO_DEFAULT_URL

class MongoDefault:
    def __init__(self):
        self._client = AsyncIOMotorClient(MONGO_DEFAULT_URL)
        self.db = self._client["hub365-os"]
        self.user_collection = self.db["users"]

    async def get_user_details(self, id):
        docs = await self.user_collection.find_one(
            {"_id": ObjectId(id)}
        )
        return docs

    async def get_company_ids(self):
        doc = await self.db["installmodels"].find_one(
            {"identifier": "com.hub365.company.models.company"},
            {"_id": 1}
        )
        return doc["_id"] if doc else None
    
    async def get_studio_ids(self):
        doc = await self.db["installmodels"].find_one(
            {"identifier": "com.hub365.studios.models.studio"},
            {"_id": 1}
        )
        return doc["_id"] if doc else None

if __name__=="__main__":
    obj = MongoDefault()
    asyncio.run(obj.get_user_details("5fb29a8e8532ea44674f38a1"))