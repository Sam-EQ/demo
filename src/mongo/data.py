from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId
import asyncio
import logging

logger =logging.getLogger(__name__)

from src.config import MONGO_DATA_URL

class MongoData():
    def __init__(self):
        self._client = AsyncIOMotorClient(MONGO_DATA_URL)
        self.db = self._client["hub365-data"]
    
    async def get_all_active_data(self, id):
        cursor = self.db[id].find({"isDeleted":False})
        docs = await cursor.to_list(length=None)
        return docs
    
    async def get_data_from_db(self, collection_id: str, id: str):
        try:
            obj_id = ObjectId(id)
            doc = await self.db[collection_id].find_one(
                {"_id": obj_id}
            )
            return doc if doc else None
        except InvalidId:
            logger.warning("Invalid ObjectId format")
            return None
        except Exception as e:
            logger.warning(f"Database error: {e}")
            return None
        
    
if __name__ == "__main__":
    obj = MongoData()
    asyncio.run(obj.get_all_active_data("5faf2b97ed9da40013909b04"))
