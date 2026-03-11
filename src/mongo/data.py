from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio
import logging

logger = logging.getLogger(__name__)

from src.config import MONGO_DATA_URL

class MongoData():
    def __init__(self):
        try:
            self._client = AsyncIOMotorClient(MONGO_DATA_URL)
        except Exception as e:
            logger.exception(f"Error in connecting with mongo for getting user data: {e}")
            raise ConnectionError(f"Error in connecting with mongo for getting user data: {e}")
        self.db = self._client["hub365-data"]
    
    async def get_all_active_users(self, id):
        try:
            cursor = self.db[id].find({"isDeleted":False})
            docs = await cursor.to_list(length=None)
            logger.info(f"Number of data processing is {len(docs)}")
            return docs
        except Exception as e:
            logger.exception(f"Error in Processing mongo data : {e}")
            raise RuntimeError(f"Error in Processing mongo data : {e}")

