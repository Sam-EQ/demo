import json
import os
import urllib3
from dotenv import load_dotenv
from opensearchpy import OpenSearch, helpers

urllib3.disable_warnings()

load_dotenv()

INDEX_NAME = "pdm_manual"

HOST = os.getenv("OPENSEARCH_URL").replace("https://", "")
USERNAME = os.getenv("OPENSEARCH_USERNAME")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD").strip('"').strip("'")

client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=(USERNAME, PASSWORD),
    use_ssl=True,
    verify_certs=False
)

with open("pdm_embeddings.json") as f:
    docs = json.load(f)

actions = []

for doc in docs:

    actions.append({
        "_index": INDEX_NAME,
        "_id": doc["chunk_id"],
        "_source": doc
    })

helpers.bulk(client, actions)

print("Upload complete")