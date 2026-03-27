# Palette RAG Pipeline

Four single-responsibility scripts. Run them in order.

```
extracted.json  →  chunks.json  →  embedded.json  →  OpenSearch
  1_extract.py     2_chunk.py      3_embed.py        4_upsert.py
```

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in your .env values
```

---

## Step 1 — Extract

Pulls ALL data from MongoDB and enriches each card in parallel:
- Credits, Projects, Team, Related cards, Comments, Resources
- Micro-knowledge card links
- Palette Projects, Practices
- Creator / Updater user info
- Bookmark counts
- Summary image → OpenAI Vision description
- Splash screen data

```bash
python 1_extract.py
python 1_extract.py --output extracted.json
python 1_extract.py --limit 10      # test with 10 cards
```

**Output:** `extracted.json`
```json
{
  "total_cards": 120,
  "total_pdfs": 85,
  "cards": [ { "id": "...", "name": "...", ... } ],
  "pdf_candidates": [ { "_id": "...", "fileId": "...", ... } ],
  "splashscreen": [ { ... } ]
}
```

---

## Step 2 — Chunk

Converts cards into index documents + downloads Hub PDFs and chunks them:

- Each card → 1 document with full enriched text
- Each PDF → N chunk documents (600-char chunks, 80-char overlap)
- Splash screen → 1 document per entry

```bash
python 2_chunk.py
python 2_chunk.py --input extracted.json --output chunks.json
python 2_chunk.py --no-pdfs          # skip PDF processing
```

**Output:** `chunks.json` — flat list of docs:
```json
[
  { "_id": "abc123", "type": "card",      "title": "...", "text": "...", "metadata": {...}, "vector_field": [] },
  { "_id": "xyz_0",  "type": "pdf_chunk", "title": "...", "text": "...", "metadata": {...}, "vector_field": [] }
]
```

---

## Step 3 — Embed

Sends `text` field of each doc to OpenAI embeddings API, fills `vector_field`.

- Batches requests (default: 50 per batch)
- Exponential back-off on rate limits
- Saves progress after every batch (safe to re-run / resume on crash)
- Skips docs that already have `vector_field`

```bash
python 3_embed.py
python 3_embed.py --input chunks.json --output embedded.json
python 3_embed.py --batch-size 100
```

**Output:** `embedded.json` — same as chunks.json but `vector_field` filled.

---

## Step 4 — Upsert

Creates the OpenSearch index (with knn_vector mapping) if needed, then bulk-upserts all docs.

```bash
python 4_upsert.py
python 4_upsert.py --input embedded.json
python 4_upsert.py --recreate-index    # drop + recreate (full re-index)
```

**Index mapping includes:**
- `vector_field` — knn_vector, cosine similarity, HNSW (nmslib)
- `metadata.*`   — all structured fields (card_type, status, practices, etc.)
- `title`, `text` — full-text search fields

---

## Full run

```bash
python 1_extract.py && \
python 2_chunk.py   && \
python 3_embed.py   && \
python 4_upsert.py
```

---

## File sizes (approximate)

| File            | Contents                          |
|-----------------|-----------------------------------|
| `extracted.json`| Raw enriched cards (~5–20 MB)     |
| `chunks.json`   | Cards + PDF chunks (~10–50 MB)    |
| `embedded.json` | + 3072-dim vectors (~200–800 MB)  |

---

## Tuning (.env)

| Variable           | Default | Notes                            |
|--------------------|---------|----------------------------------|
| `CARD_CONCURRENCY` | 10      | Parallel card enrichments        |
| `PDF_CONCURRENCY`  | 5       | Parallel PDF downloads           |
| `EMBEDDING_BATCH_SIZE` | 50  | Docs per OpenAI API call         |
| `EMBEDDING_MODEL`  | text-embedding-3-large | Or text-embedding-3-small |
| `EMBEDDING_DIMENSIONS` | 3072 | 3072 for large, 1536 for small |