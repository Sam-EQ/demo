"""
SCRIPT 4 — upsert.py
=====================
Reads embedded.json and bulk-upserts all docs into OpenSearch.
Creates the index with correct knn_vector mapping if it doesn't exist.

Run:
  python upsert.py
  python upsert.py --input embedded.json
  python upsert.py --recreate-index      # drop + recreate the index first
"""
import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, Generator, List

from opensearchpy import OpenSearch, helpers, RequestError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upsert")

try:
    import config as cfg
except Exception as e:
    sys.exit(f"config.py not found or invalid: {e}")

INPUT_FILE  = "embedded.json"
CHUNK_SIZE  = 200   # docs per bulk request


# ─────────────────────────────────────────────────────────────────────────────
# OpenSearch client
# ─────────────────────────────────────────────────────────────────────────────

def _client() -> OpenSearch:
    auth = None
    if cfg.OPENSEARCH_USERNAME and cfg.OPENSEARCH_PASSWORD:
        auth = (cfg.OPENSEARCH_USERNAME, cfg.OPENSEARCH_PASSWORD)
    return OpenSearch(
        hosts=[cfg.OPENSEARCH_URL],
        http_auth=auth,
        use_ssl=cfg.OPENSEARCH_URL.startswith("https"),
        verify_certs=cfg.OPENSEARCH_VERIFY_SSL,
        timeout=60,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Index mapping  (knn_vector + all metadata fields)
# ─────────────────────────────────────────────────────────────────────────────

def _index_body() -> Dict:
    return {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 512,
                "number_of_shards":   1,
                "number_of_replicas": 1,
            }
        },
        "mappings": {
            "properties": {
                # ── Vector ────────────────────────────────────────────────
                "vector_field": {
                    "type":   "knn_vector",
                    "dimension": cfg.EMBEDDING_DIMENSIONS,
                    "method": {
                        "name":       "hnsw",
                        "space_type": "cosinesimil",
                        "engine":     "nmslib",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                # ── Top-level ─────────────────────────────────────────────
                "type":      {"type": "keyword"},
                "paletteId": {"type": "keyword"},
                "title":     {"type": "text",
                              "fields": {"keyword": {"type": "keyword"}}},
                "text":      {"type": "text"},
                # ── Metadata ──────────────────────────────────────────────
                "metadata": {
                    "properties": {
                        "id":                    {"type": "keyword"},
                        "title":                 {"type": "text",
                                                  "fields": {"keyword": {"type": "keyword"}}},
                        "card_type":             {"type": "keyword"},
                        "status":                {"type": "keyword"},
                        "shortDescription":      {"type": "text"},
                        "keywords":              {"type": "keyword"},
                        "stages":                {"type": "keyword"},
                        "practices":             {"type": "keyword"},
                        "livingDesignPetals":    {"type": "keyword"},
                        "certificationCategory": {"type": "keyword"},
                        "certificationType":     {"type": "keyword"},
                        "isPinToTop":            {"type": "boolean"},
                        "bookmark_count":        {"type": "integer"},
                        "publishDate":           {"type": "date", "ignore_malformed": True},
                        "reviewDate":            {"type": "date", "ignore_malformed": True},
                        "createdAt":             {"type": "date", "ignore_malformed": True},
                        "updatedAt":             {"type": "date", "ignore_malformed": True},
                        "creator_name":          {"type": "keyword"},
                        "creator_email":         {"type": "keyword"},
                        "updator_name":          {"type": "keyword"},
                        "updator_email":         {"type": "keyword"},
                        "summary_text":          {"type": "text"},
                        "summary_image_url":     {"type": "keyword"},
                        "image_description":     {"type": "text"},
                        "appURL":                {"type": "keyword"},
                        "softwaresUsed":         {"type": "keyword"},
                        "features":              {"type": "keyword"},
                        # PDF chunk extra fields
                        "resource_id":           {"type": "keyword"},
                        "chunk_index":           {"type": "integer"},
                        "total_chunks":          {"type": "integer"},
                        "fileType":              {"type": "keyword"},
                        "link":                  {"type": "keyword"},
                    }
                },
            }
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Index management
# ─────────────────────────────────────────────────────────────────────────────

def ensure_index(os: OpenSearch, recreate: bool = False) -> None:
    index = cfg.OPENSEARCH_INDEX
    exists = os.indices.exists(index=index)

    if exists and recreate:
        log.info("Deleting existing index: %s", index)
        os.indices.delete(index=index)
        exists = False

    if not exists:
        log.info("Creating index: %s  (dim=%d)", index, cfg.EMBEDDING_DIMENSIONS)
        try:
            os.indices.create(index=index, body=_index_body())
            log.info("✓ Index created: %s", index)
        except RequestError as exc:
            log.error("Index creation failed: %s", exc)
            raise
    else:
        log.info("Index already exists: %s", index)


# ─────────────────────────────────────────────────────────────────────────────
# Bulk upsert
# ─────────────────────────────────────────────────────────────────────────────

def _actions(docs: List[Dict], index: str) -> Generator[Dict, None, None]:
    for doc in docs:
        doc_id = doc.get("_id")
        if not doc_id:
            continue
        body = {k: v for k, v in doc.items() if k != "_id"}
        yield {
            "_op_type": "index",
            "_index":   index,
            "_id":      str(doc_id),
            **body,
        }


def upsert_all(os: OpenSearch, docs: List[Dict]) -> None:
    index  = cfg.OPENSEARCH_INDEX
    total  = len(docs)
    done   = 0
    errors = 0
    t0     = time.time()

    success, failed = helpers.bulk(
        os,
        _actions(docs, index),
        chunk_size=CHUNK_SIZE,
        raise_on_error=False,
        raise_on_exception=False,
    )

    errors = len(failed) if failed else 0
    elapsed = time.time() - t0

    log.info("✓ Upserted %d docs  |  Errors: %d  |  Time: %.1fs", success, errors, elapsed)

    if failed:
        log.warning("First 5 errors:")
        for err in (failed or [])[:5]:
            log.warning("  %s", err)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Upsert embedded Palette docs into OpenSearch")
    ap.add_argument("--input",          default=INPUT_FILE, help=f"Input JSON (default: {INPUT_FILE})")
    ap.add_argument("--recreate-index", action="store_true", help="Drop and recreate the index")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        docs = json.load(f)

    # Warn if docs are missing embeddings
    missing = sum(1 for d in docs if not d.get("vector_field"))
    if missing:
        log.warning("%d docs have no vector_field — run embed.py first", missing)

    log.info("Loaded %d docs from %s", len(docs), args.input)

    os = _client()
    ensure_index(os, recreate=args.recreate_index)
    upsert_all(os, docs)


if __name__ == "__main__":
    main()