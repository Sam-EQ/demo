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

count = client.count(index=INDEX_NAME)

print("Documents in index:", count["count"])