import asyncio
import json
import sys

from dotenv import load_dotenv
from opensearchpy._async.client import AsyncOpenSearch
import logging

logger = logging.getLogger(__name__)

from src.config import OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD, INDEX_NAME

class OpenSearchClient:
    def __init__(self):
        try:
            self._client = AsyncOpenSearch(
                hosts=[""],
                http_auth=(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD),
                use_ssl=True,
                verify_certs=False,
                timeout=60,
                max_retries=5,
                retry_on_timeout=True,
            )
        except Exception as e:
            logger.info(f"Error in OpenSearch connectivity {e}")
            raise ConnectionError(f"Error in OpenSearch connectivity {e}")
 
    async def get_all_data(self, index_name = None):
        try:
            if not index_name :
                index_name = INDEX_NAME
            response = await self._client.search(
                index=index_name,
                body={
                    "query": {
                        "match_all": {}
                    }
                }
            )
            return response
        except Exception as e:
            logger.exception(f"Error in fetching data in opensearch {e}")
            raise RuntimeError(f"Error in fetching data in opensearch {e}")

    async def close(self):
        try:
            await self._client.close()
        except Exception as e:
            logger.exception(f"Error in closing the opensearch connectivity {e}")


async def main():
    obj = OpenSearchClient()
    data = await obj.get_all_data()
    with open("test_opensearch_output.json", "w") as f:
        json.dump(data, f, indent=4)
    await obj.close()


if __name__ == "__main__":
    asyncio.run(main())
