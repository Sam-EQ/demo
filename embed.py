"""
SCRIPT 3 — embed.py
====================
Reads chunks.json, adds OpenAI vector embeddings to each doc's vector_field.
Writes: → embedded.json

Skips docs that already have a non-empty vector_field (safe to re-run / resume).

Run:
  python embed.py
  python embed.py --input chunks.json --output embedded.json
  python embed.py --batch-size 100
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from typing import List

from openai import AsyncOpenAI, RateLimitError, APIStatusError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("embed")

try:
    import config as cfg
except Exception as e:
    sys.exit(f"config.py not found or invalid: {e}")

INPUT_FILE  = "chunks.json"
OUTPUT_FILE = "embedded.json"
MAX_RETRIES = 6
RETRY_BASE  = 2.0   # seconds


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI embedding with retry
# ─────────────────────────────────────────────────────────────────────────────

async def _embed_batch(client: AsyncOpenAI, texts: List[str]) -> List[List[float]]:
    cleaned = [(t or "").replace("\n", " ").strip() for t in texts]
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.embeddings.create(
                input=cleaned,
                model=cfg.EMBEDDING_MODEL,
                dimensions=cfg.EMBEDDING_DIMENSIONS,
            )
            return [item.embedding for item in resp.data]
        except RateLimitError:
            wait = RETRY_BASE ** attempt
            log.warning("Rate limit hit — waiting %.1fs (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
        except APIStatusError as exc:
            if exc.status_code in (500, 502, 503, 504):
                wait = RETRY_BASE ** attempt
                log.warning("OpenAI %d — waiting %.1fs", exc.status_code, wait)
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Embedding failed after {MAX_RETRIES} attempts")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(input_path: str, output_path: str, batch_size: int):
    with open(input_path, encoding="utf-8") as f:
        docs = json.load(f)

    # Only embed docs that have text and no existing vector
    to_embed = [(i, d) for i, d in enumerate(docs)
                if d.get("text") and not d.get("vector_field")]
    already  = len(docs) - len(to_embed)

    log.info("Total docs: %d  |  To embed: %d  |  Already embedded: %d",
             len(docs), len(to_embed), already)

    if not to_embed:
        log.info("Nothing to embed. Writing output as-is.")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)
        return

    client       = AsyncOpenAI(api_key=cfg.OPENAI_KEY)
    total_batches = (len(to_embed) + batch_size - 1) // batch_size
    t0           = time.time()

    for b, start in enumerate(range(0, len(to_embed), batch_size), 1):
        batch   = to_embed[start: start + batch_size]
        texts   = [d["text"] for _, d in batch]
        vectors = await _embed_batch(client, texts)

        for (orig_idx, doc), vec in zip(batch, vectors):
            docs[orig_idx]["vector_field"] = vec

        elapsed = time.time() - t0
        log.info("  Batch %d / %d  (%d docs)  elapsed: %.1fs",
                 b, total_batches, len(batch), elapsed)

        # Save progress after every batch so we can resume on crash
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False)

    log.info("✓ Embedded %d docs → %s  (total: %.1fs)",
             len(to_embed), output_path, time.time() - t0)


def main():
    ap = argparse.ArgumentParser(description="Add OpenAI embeddings to chunked Palette docs")
    ap.add_argument("--input",      default=INPUT_FILE,  help=f"Input JSON (default: {INPUT_FILE})")
    ap.add_argument("--output",     default=OUTPUT_FILE, help=f"Output JSON (default: {OUTPUT_FILE})")
    ap.add_argument("--batch-size", type=int, default=cfg.EMBEDDING_BATCH_SIZE,
                    help=f"Embedding batch size (default: {cfg.EMBEDDING_BATCH_SIZE})")
    args = ap.parse_args()
    asyncio.run(run(args.input, args.output, args.batch_size))


if __name__ == "__main__":
    main()