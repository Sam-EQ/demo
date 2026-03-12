import os
import json
import urllib3
from dotenv import load_dotenv
from opensearchpy import OpenSearch
from openai import OpenAI

urllib3.disable_warnings()

load_dotenv()

INDEX_NAME = "pdm_manual"

HOST = os.getenv("OPENSEARCH_URL").replace("https://", "")
USERNAME = os.getenv("OPENSEARCH_USERNAME")
PASSWORD = os.getenv("OPENSEARCH_PASSWORD").strip('"').strip("'")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenSearch(
    hosts=[{"host": HOST, "port": 443}],
    http_auth=(USERNAME, PASSWORD),
    use_ssl=True,
    verify_certs=False
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_embedding(text):

    response = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )

    return response.data[0].embedding


def search_opensearch(query_embedding):

    body = {
        "size": 5,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": 5
                }
            }
        }
    }

    result = client.search(
        index=INDEX_NAME,
        body=body
    )

    return result["hits"]["hits"]


def ask_llm(question, context):

    prompt = f"""
Answer the question using ONLY the provided context.

Context:
{context}

Question:
{question}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You answer questions about the Project Delivery Manual."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


def main():

    question = input("\nAsk a question about the PDM:\n\n> ")

    print("\nGenerating embedding...")

    query_embedding = get_embedding(question)

    print("Searching OpenSearch...")

    hits = search_opensearch(query_embedding)

    print("\nTop Retrieved Chunks:\n")

    context = ""

    for i, hit in enumerate(hits):

        source = hit["_source"]

        print(f"{i+1}. {source['title']}")
        print(source["text"][:200], "...\n")

        context += source["text"] + "\n\n"

    print("\nGenerating answer...\n")

    answer = ask_llm(question, context)

    print("Answer:\n")
    print(answer)


if __name__ == "__main__":
    main()