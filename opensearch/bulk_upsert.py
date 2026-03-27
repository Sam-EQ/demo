"""
Bulk upsert index documents to OpenSearch. All work is in memory; optional debug dump to file.

Usage from pipeline (in-memory):
  from opensearch.bulk_upsert import bulk_upsert_index_docs
  await bulk_upsert_index_docs(all_index_docs, add_embeddings=True)

Standalone / debug:
  python -m opensearch.bulk_upsert output_index.json   # load from file, upsert, no dump
  python -m opensearch.bulk_upsert output_index.json --debug-dump  # also write back to file
  python -m opensearch.bulk_upsert --embed-only output_index.json  # add embeddings and dump
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opensearchpy import OpenSearch, helpers

from src.config import (
    OPENSEARCH_URL,
    OPENSEARCH_USERNAME,
    OPENSEARCH_PASSWORD,
    INDEX_NAME,
    OPENSEARCH_VERIFY_SSL,
)

logger = logging.getLogger(__name__)

# Optional: write index docs to file only when set (debug)
DEBUG_WRITE_INDEX = os.getenv("DEBUG_WRITE_INDEX", "").strip().lower() in ("1", "true", "yes")


def _opensearch_client():
    """Build OpenSearch client from config."""
    if not OPENSEARCH_URL:
        raise ValueError("OPENSEARCH_URL is not set")
    auth = None
    if OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD:
        auth = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
    return OpenSearch(
        hosts=[OPENSEARCH_URL],
        http_auth=auth,
        use_ssl=OPENSEARCH_URL.startswith("https"),
        verify_certs=OPENSEARCH_VERIFY_SSL,
    )


def _bulk_actions(docs: list, index: str = None):
    """Yield bulk index actions for opensearch-py helpers.bulk. Each doc must have _id."""
    idx = index or INDEX_NAME
    for doc in docs:
        doc_id = doc.get("_id")
        if doc_id is None:
            continue
        body = {k: v for k, v in doc.items() if k != "_id"}
        yield {"_index": idx, "_id": str(doc_id), **body}


def bulk_upsert_sync(docs: list, index: str = None) -> tuple:
    """
    Synchronous bulk upsert: index all docs to OpenSearch (upsert by _id).
    docs: list of dicts with _id, and optionally text, metadata, vector_field, etc.
    Returns (success_count, error_count).
    """
    if not docs:
        return 0, 0
    client = _opensearch_client()
    idx = index or INDEX_NAME
    success, failed = helpers.bulk(
        client,
        _bulk_actions(docs, idx),
        chunk_size=100,
        raise_on_error=False,
        raise_on_exception=False,
    )
    return success, len(failed) if failed else 0


async def add_embeddings_to_docs(docs: list) -> list:
    """Add vector_field to each doc that has text but no vector_field. Modifies in place."""
    from src.llm_models.embeddings import add_embeddings_to_records
    to_embed = [d for d in docs if (d.get("text") and not d.get("vector_field"))]
    if not to_embed:
        return docs
    await add_embeddings_to_records(to_embed)
    return docs


async def bulk_upsert_index_docs(
    docs: list,
    index: str = None,
    add_embeddings: bool = True,
    debug_dump_path: str = None,
) -> tuple:
    """
    In-memory: optionally add embeddings to docs missing vector_field, then bulk upsert to OpenSearch.
    debug_dump_path: if set (e.g. output_index.json), write docs to file for debugging only.
    Returns (success_count, error_count).
    """
    if not docs:
        return 0, 0
    if add_embeddings:
        await add_embeddings_to_docs(docs)
    success, err_count = bulk_upsert_sync(docs, index=index)
    if debug_dump_path or DEBUG_WRITE_INDEX:
        path = debug_dump_path or "output_index.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, default=str, ensure_ascii=False)
        logger.info("Debug: written %d docs to %s", len(docs), path)
    return success, err_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bulk upsert index docs to OpenSearch (in-memory; optional debug dump)")
    parser.add_argument("input_file", nargs="?", help="JSON file of index docs (for standalone run); if omitted, use from pipeline only")
    parser.add_argument("--index", default=INDEX_NAME, help="OpenSearch index name")
    parser.add_argument("--no-embed", action="store_true", help="Skip adding embeddings")
    parser.add_argument("--debug-dump", action="store_true", help="Write docs to output_index.json after upsert (debug)")
    args = parser.parse_args()

    if not args.input_file:
        print("Usage: python -m opensearch.bulk_upsert <input_file.json> [--no-embed] [--debug-dump]", file=sys.stderr)
        sys.exit(1)

    path = Path(args.input_file)
    if not path.exists():
        print("File not found:", args.input_file, file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    if not isinstance(docs, list):
        docs = [docs]

    async def run():
        return await bulk_upsert_index_docs(
            docs,
            index=args.index,
            add_embeddings=not args.no_embed,
            debug_dump_path="output_index.json" if args.debug_dump else None,
        )

    success, err_count = asyncio.run(run())
    print("Upserted:", success, "errors:", err_count)
    if err_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
