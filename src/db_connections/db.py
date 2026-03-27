import logging
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from src.config import (
    MONGO_DATA_URI,
    MONGO_DEFAULT_URI,
    DATA_DB_NAME,
    DEFAULT_DB_NAME,
    MKBOOKMARK,
)

logger = logging.getLogger(__name__)

class MongoService:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoService, cls).__new__(cls)
            cls._instance.data_client = AsyncIOMotorClient(MONGO_DATA_URI)
            cls._instance.os_client = AsyncIOMotorClient(MONGO_DEFAULT_URI)
            cls._instance.data_db = cls._instance.data_client[DATA_DB_NAME]
            cls._instance.os_db = cls._instance.os_client[DEFAULT_DB_NAME]
        return cls._instance

    async def get_all_records(self, coll: str, query: dict = None):
        q = {"isDeleted": False}
        if query: q.update(query)
        return await self.data_db[coll].find(q).to_list(length=None)

    async def get_single_record(self, coll: str, record_id: str):
        try:
            return await self.data_db[coll].find_one({"_id": ObjectId(str(record_id)), "isDeleted": False})
        except: return None

    async def get_many_by_ids(self, coll: str, ids: list):
        if not ids: return []
        oids = [ObjectId(str(i)) for i in ids if i]
        return await self.data_db[coll].find({"_id": {"$in": oids}, "isDeleted": False}).to_list(length=None)

    async def get_user(self, user_id: str):
        try:
            user = await self.os_db["users"].find_one({"_id": ObjectId(str(user_id))})
            if not user: return None
            name = user.get("name", {})
            return {
                "name": f"{name.get('first', '')} {name.get('last', '')}".strip() or "Unknown",
                "email": user.get("email")
            }
        except: return None

    async def get_bookmark_counts(self):
        """Aggregate bookmark counts by microknowledgeId; keys are str(microknowledgeId) for lookup by mk_id."""
        if not MKBOOKMARK:
            logger.warning("MKBOOKMARK not set in config; bookmark counts will be 0.")
            return {}
        # Group by microknowledgeId (field may be microknowledgeId or microKnowldgeId in DB)
        pipeline = [
            {"$match": {"isDeleted": False}},
            {"$group": {"_id": "$microknowledgeId", "count": {"$sum": 1}}},
        ]
        try:
            cursor = self.data_db[MKBOOKMARK].aggregate(pipeline)
            results = await cursor.to_list(length=None)
            return {str(r["_id"]): r["count"] for r in results if r.get("_id") is not None}
        except Exception as e:
            # If microknowledgeId doesn't exist, try common typo used in codebase
            logger.warning("Bookmark aggregation with microknowledgeId failed: %s", e)
            pipeline[1]["$group"]["_id"] = "$microknowldgeId"
            cursor = self.data_db[MKBOOKMARK].aggregate(pipeline)
            results = await cursor.to_list(length=None)
            return {str(r["_id"]): r["count"] for r in results if r.get("_id") is not None}
    # --- Close connection ---

    @classmethod
    def close(cls):
        """Close both database connections when the app shuts down."""
        if cls._instance:
            cls._instance.data_client.close()
            cls._instance.default_client.close()
            logger.info("MongoDB connections closed.")