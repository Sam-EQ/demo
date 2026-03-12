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

BATCH_SIZE = 50

client = OpenSearch(
    hosts=[{
        "host": HOST,
        "port": 443
    }],
    http_auth=(USERNAME, PASSWORD),
    use_ssl=True,
    verify_certs=False,
    timeout=120,
    max_retries=3,
    retry_on_timeout=True
)


def chunk_list(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def main():

    print("\nConnecting to OpenSearch...\n")

    try:
        info = client.info()
        print("Connected to OpenSearch cluster:", info["cluster_name"])
    except Exception as e:
        print("Connection failed:", e)
        return

    with open("pdm_embeddings.json") as f:
        docs = json.load(f)

    print("\nTotal documents:", len(docs), "\n")

    total_indexed = 0

    for batch in chunk_list(docs, BATCH_SIZE):

        actions = []

        for doc in batch:

            actions.append({
                "_index": INDEX_NAME,
                "_id": doc["chunk_id"],
                "_source": doc
            })

        helpers.bulk(
            client,
            actions,
            request_timeout=120
        )

        total_indexed += len(actions)

        print(f"Indexed {total_indexed}/{len(docs)}")

    print("\nUpload complete")


if __name__ == "__main__":
    main()