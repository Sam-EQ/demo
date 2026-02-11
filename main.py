from dotenv import load_dotenv
load_dotenv()

from src.pipeline import Pipeline
import asyncio

obj = Pipeline()

asyncio.run(obj.run())
