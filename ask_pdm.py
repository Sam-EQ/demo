import os
import urllib3
from dotenv import load_dotenv
from opensearchpy import OpenSearch
from openai import OpenAI

urllib3.disable_warnings()

load_dotenv()

INDEX_NAME = "pdm_manual"

HOST = os.getenv("OPENSEARCH_URL").replace("https://", "")
USERNAME = os.getenv("OPENSEARCH_USERNAME")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=(USERNAME, PASSWORD),
    use_ssl=True,
    verify_certs=False
)


def get_embedding(text):

    r = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )

    return r.data[0].embedding


def search(vector):

    body = {
        "size": 5,
        "query": {
            "knn": {
                "embedding": {
                    "vector": vector,
                    "k": 5
                }
            }
        }
    }

    return client.search(index=INDEX_NAME, body=body)


def main():

    question = input("\nAsk a question:\n\n> ")

    emb = get_embedding(question)

    res = search(emb)

    context = ""

    for hit in res["hits"]["hits"]:

        src = hit["_source"]

        print("\nSOURCE:", src["title"])

        print(src["text"][:200])

        context += src["text"] + "\n\n"

    answer = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer using provided context"},
            {"role": "user", "content": context + "\nQuestion:" + question}
        ]
    )

    print("\nAnswer:\n")
    print(answer.choices[0].message.content)


if __name__ == "__main__":
    main()