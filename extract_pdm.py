import asyncio
import json
import os

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_DATA_URL = os.getenv("MONGO_DATA_URL")

COLLECTION = "64c0ab8f0339a238341b61b8"


async def extract():

    client = AsyncIOMotorClient(MONGO_DATA_URL)
    db = client["hub365-data"]

    cursor = db[COLLECTION].find({"isDeleted": False})

    articles = []

    async for doc in cursor:

        article = {
            "id": str(doc["_id"]),
            "title": doc.get("name"),
            "parentId": str(doc["parentId"]) if doc.get("parentId") else None,
            "sortOrder": doc.get("sortOrder"),
            "countries": doc.get("countries"),
            "content": doc.get("values")
        }

        articles.append(article)

    with open("pdm_articles.json", "w") as f:
        json.dump(articles, f, indent=2)

    print("Export complete")
    print("Articles:", len(articles))


if __name__ == "__main__":
    asyncio.run(extract())