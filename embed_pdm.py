import json
import os
import spacy
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

nlp = spacy.load("en_core_web_sm")


def split_text(text, max_tokens=500):

    enc = tiktoken.encoding_for_model("text-embedding-3-large")

    sentences = [s.text.strip() for s in nlp(text).sents if s.text.strip()]

    chunks = []
    current = []
    tokens = 0

    for sentence in sentences:

        sent_tokens = len(enc.encode(sentence))

        if tokens + sent_tokens > max_tokens:
            chunks.append(" ".join(current))
            current = []
            tokens = 0

        current.append(sentence)
        tokens += sent_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def embed(text):

    r = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )

    return r.data[0].embedding


def main():

    with open("pdm_articles.json") as f:
        articles = json.load(f)

    dataset = []

    for article in articles:

        text = article["content"]

        for img in article["images"]:
            text += f"\n\nIMAGE DESCRIPTION:\n{img['description']}"

        chunks = split_text(text)

        for i, chunk in enumerate(chunks):

            emb = embed(chunk)

            dataset.append({
                "article_id": article["id"],
                "title": article["title"],
                "chunk_id": f"{article['id']}_{i}",
                "text": chunk,
                "embedding": emb
            })

    with open("pdm_embeddings.json", "w") as f:
        json.dump(dataset, f)

    print("Embedding complete")
    print("Total chunks:", len(dataset))


if __name__ == "__main__":
    main()