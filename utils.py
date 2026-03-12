import spacy
import tiktoken
from math import floor

try:
    nlp = spacy.load("en_core_web_sm")
except:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


def split_text(text, max_tokens=8000):

    doc = nlp(text)
    sentences = [s.text.strip() for s in doc.sents if s.text.strip()]

    enc = tiktoken.encoding_for_model("gpt-4o")

    chunks = []
    current = []
    token_count = 0

    for sent in sentences:

        tokens = len(enc.encode(sent))

        if token_count + tokens > max_tokens:
            chunks.append(" ".join(current))
            current = []
            token_count = 0

        current.append(sent)
        token_count += tokens

    if current:
        chunks.append(" ".join(current))

    return chunks