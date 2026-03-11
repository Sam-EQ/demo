from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio
import logging

logger = logging.getLogger(__name__)

from src.config import MONGO_DEFAULT_URL
from pymongo.errors import PyMongoError

class MongoDefault:
    def __init__(self):
        try:
            self._client = AsyncIOMotorClient(MONGO_DEFAULT_URL)
        except Exception as e:
            logger.exception(f"Error in connecting with mongo for getting user data: {e}")
            raise ConnectionError(f"Error in connecting with mongo for getting user data: {e}")
        self.db = self._client["hub365-os"]
        self.user_collection = self.db["users"]

    async def get_user_details(self, id):
        try:
            docs = await self.user_collection.find_one(
                {"_id": ObjectId(id)}
            )
            return docs
        except PyMongoError as e:
            logger.exception(f"Error in get user details : {e}")
            raise RuntimeError(f"Error in connecting with mongo for getting user data: {e}")

