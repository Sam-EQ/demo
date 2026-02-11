import asyncio

from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from talent_toolkit.src.llm.openai_client import get_embedding
from src.config import OPENSEARCH_USERNAME,OPENSEARCH_PASSWORD
from talent_toolkit.src.utils.utils import make_json_safe
from src.config import *
from src.process.benefits import Benefits

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

class Pipeline():
    def __init__(self):
        self._mongo_data = MongoData()
        self._mongo_default = MongoDefault()
        self.open_search_client = OpenSearch(
            hosts=["https://search-ai-test-domain-343yonb3wnzzilhdnlbn3cdesm.us-west-1.es.amazonaws.com"],
            http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
            use_ssl=True,
            verify_certs=False,
            timeout=60,
            max_retries=5,
            retry_on_timeout=True )
        self.benefits = Benefits()

    async def _need_to_process(self):
        process = ['BENEFITS' ,'POLICIES']
        return process
        
    async def run(self):
        process_data = self._need_to_process()
        final_result = []
        if "BENEFITS" in process_data:
            result = self.benefits.process()
            final_result.extend(result)
        elif "POLICIES" in process_data:
            pass
            # result = self.policies.process(e)
        
        actions = [
            {
                "_index": "talent_toolkit",
                "_source": {
                    "id": str(doc["id"]),
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "vector_field": doc["vector_field"]
                }
            }
            for doc in final_result
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: bulk(
                self.open_search_client,
                actions,
                chunk_size=200,
                request_timeout=60
            )
        )
        bulk(self.open_search_client, actions)

