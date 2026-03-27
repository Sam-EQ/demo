# debug_mongo.py  — run this in the palette_app folder
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_DATA_URI"])
    db = client["hub365-data"]
    
    # List all collections
    print("=== Collections in hub365-data ===")
    for name in await db.list_collection_names():
        count = await db[name].count_documents({})
        print(f"  {name}: {count} docs")
    
    # Check the microknowledge collection with no filter
    COLL = os.environ.get("MICROKNOWLEDGE", "microknowledge")
    print(f"\n=== First doc in '{COLL}' (no filter) ===")
    doc = await db[COLL].find_one({})
    if doc:
        print("Keys:", list(doc.keys()))
        print("isDeleted:", doc.get("isDeleted"))
    else:
        print("Collection is EMPTY or doesn't exist")

asyncio.run(main())