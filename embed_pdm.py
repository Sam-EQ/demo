import json
import os
import spacy
import tiktoken
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    nlp = spacy.load("en_core_web_sm")
except:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
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


def build_section_path(article, lookup):

    path = [article["title"]]

    parent = article["parentId"]

    while parent:

        parent_article = lookup.get(parent)

        if not parent_article:
            break

        path.append(parent_article["title"])

        parent = parent_article["parentId"]

    return " > ".join(reversed(path))


def main():

    with open("pdm_articles.json") as f:
        articles = json.load(f)

    # lookup table
    lookup = {a["id"]: a for a in articles}

    dataset = []

    for article in articles:

        content = article["content"]

        if not content:
            continue

        section_path = build_section_path(article, lookup)

        chunks = split_text(content)

        for i, chunk in enumerate(chunks):

            emb = embed(chunk)

            dataset.append({
                "article_id": article["id"],
                "title": article["title"],
                "section_path": section_path,
                "parent_id": article["parentId"],
                "sort_order": article["sortOrder"],
                "countries": article["countries"],
                "chunk_id": f"{article['id']}_{i}",
                "chunk_index": i,
                "text": chunk,
                "embedding": emb
            })

    with open("pdm_embeddings.json","w") as f:
        json.dump(dataset,f)

    print("Embedding complete")
    print("Total chunks:", len(dataset))


if __name__ == "__main__":
    main()