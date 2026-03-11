from dotenv import load_dotenv
load_dotenv() 

from src.pipeline import Pipeline
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

try:    
    logger.info("Starting pipeline run")
    obj = Pipeline()
    asyncio.run(obj.run("64c0ab8f0339a238341b61b8"))
    logger.info("Pipeline completed successfully")
except Exception as e:
    logger.exception("Pipeline execution failed")
    raise

