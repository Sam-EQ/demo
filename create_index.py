import os
import urllib3
from dotenv import load_dotenv
from opensearchpy import OpenSearch

urllib3.disable_warnings()

load_dotenv()

INDEX_NAME = "pdm_manual"

HOST = os.getenv("OPENSEARCH_URL").replace("https://", "")
USERNAME = os.getenv("OPENSEARCH_USERNAME")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=(USERNAME, PASSWORD),
    use_ssl=True,
    verify_certs=False
)

mapping = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "article_id": {"type": "keyword"},
            "title": {"type": "text"},
            "text": {"type": "text"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 3072
            }
        }
    }
}

if client.indices.exists(index=INDEX_NAME):
    client.indices.delete(index=INDEX_NAME)

client.indices.create(index=INDEX_NAME, body=mapping)

print("Index created")