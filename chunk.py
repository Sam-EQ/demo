"""
SCRIPT 2 — chunk.py
====================
Reads extracted.json and produces:
  → chunks.json   (flat list of index-ready documents, one per card OR per PDF chunk)

Each document shape:
  {
    "_id":           str,         # unique; card id or "{resource_id}_{chunk_index}"
    "type":          "card" | "pdf_chunk" | "splashscreen",
    "paletteId":     str | null,  # parent card id for pdf_chunk
    "title":         str,
    "text":          str,         # full text sent to embedding model
    "metadata":      { ... },     # all structured fields, stored in OpenSearch
    "vector_field":  []           # filled by embed.py
  }

Run:
  python chunk.py
  python chunk.py --input extracted.json --output chunks.json
  python chunk.py --no-pdfs          # skip PDF download/chunking
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional

import aiohttp
import fitz  # pymupdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chunk")

try:
    import config as cfg
except Exception as e:
    sys.exit(f"config.py not found or invalid: {e}")

INPUT_FILE  = "extracted.json"
OUTPUT_FILE = "chunks.json"
CHUNK_SIZE    = 600
CHUNK_OVERLAP = 80


# ─────────────────────────────────────────────────────────────────────────────
# Card → index document
# ─────────────────────────────────────────────────────────────────────────────

def _card_text(rec: Dict) -> str:
    """Build the full text field used for embedding a card."""
    parts = []

    # Title + card type
    if rec.get("name"):
        parts.append(f"# {rec['name']}")
    if rec.get("card_type"):
        parts.append(f"Card Type: {rec['card_type']}")
    if rec.get("status"):
        parts.append(f"Status: {rec['status']}")

    # Descriptions
    if rec.get("shortDescription"):
        parts.append(f"\n## Short Description\n{rec['shortDescription']}")

    summary = rec.get("summary") or {}
    if summary.get("text"):
        parts.append(f"\n## Summary\n{summary['text']}")
    if summary.get("image_description"):
        parts.append(f"Image: {summary['image_description']}")

    # Keywords / stages / practices
    if rec.get("keywords"):
        parts.append(f"\nKeywords: {', '.join(rec['keywords'])}")
    if rec.get("stages"):
        parts.append(f"Stages: {', '.join(rec['stages'])}")
    if rec.get("practices"):
        parts.append(f"Practices: {', '.join(rec['practices'])}")

    # Living design / certifications
    if rec.get("livingDesignPetals"):
        parts.append(f"Living Design Petals: {', '.join(rec['livingDesignPetals'])}")
    if rec.get("certificationCategory"):
        parts.append(f"Certification Category: {rec['certificationCategory']}")
    if rec.get("certificationType"):
        parts.append(f"Certification Type: {rec['certificationType']}")

    # Related cards
    related = rec.get("related_cards") or []
    if related:
        names = [r["name"] for r in related if r.get("name")]
        parts.append(f"\nRelated Cards: {', '.join(names)}")

    # Credits
    credits = rec.get("credits") or []
    if credits:
        lines = [f"  - {c.get('name')} ({c.get('certification')}, {c.get('ratingSystem')})"
                 for c in credits if c.get("name")]
        if lines:
            parts.append("\nCredits:\n" + "\n".join(lines))

    # Resources summary
    resources = rec.get("resources") or []
    if resources:
        lines = []
        for r in resources:
            ft   = r.get("fileType", "")
            link = r.get("link") or ""
            t    = r.get("title") or ""
            lines.append(f"  - [{ft}] {t} {link}".strip())
        parts.append("\nResources:\n" + "\n".join(lines))

    # Palette MK links (micro-knowledge cards)
    mk_links = rec.get("palette_mk_links") or []
    if mk_links:
        titles = [l["card"]["title"] for l in mk_links if (l.get("card") or {}).get("title")]
        if titles:
            parts.append(f"\nMicro-knowledge Cards: {', '.join(titles)}")

    # Team
    team = rec.get("team") or []
    if team:
        names = [t["person"]["name"] for t in team if (t.get("person") or {}).get("name")]
        if names:
            parts.append(f"\nTeam: {', '.join(names)}")

    # Creator / updater
    if rec.get("creator_name") or rec.get("creator_email"):
        parts.append(f"\nCreated by: {rec.get('creator_name','')} <{rec.get('creator_email','')}>")
    if rec.get("updator_name") or rec.get("updator_email"):
        parts.append(f"Updated by: {rec.get('updator_name','')} <{rec.get('updator_email','')}>")

    return "\n".join(parts).strip()


def card_to_doc(rec: Dict) -> Dict:
    summary  = rec.get("summary") or {}
    metadata = {
        "id":                    rec["id"],
        "title":                 rec.get("name"),
        "card_type":             rec.get("card_type"),
        "status":                rec.get("status"),
        "shortDescription":      rec.get("shortDescription"),
        "keywords":              rec.get("keywords"),
        "stages":                rec.get("stages"),
        "practices":             rec.get("practices"),
        "livingDesignPetals":    rec.get("livingDesignPetals"),
        "certificationCategory": rec.get("certificationCategory"),
        "certificationType":     rec.get("certificationType"),
        "expertEffortTime":      rec.get("expertEffortTime"),
        "staffEffortTime":       rec.get("staffEffortTime"),
        "softwaresUsed":         rec.get("softwaresUsed"),
        "features":              rec.get("features"),
        "appURL":                rec.get("appURL"),
        "isPinToTop":            rec.get("isPinToTop"),
        "publishDate":           rec.get("publishDate"),
        "reviewDate":            rec.get("reviewDate"),
        "createdAt":             rec.get("createdAt"),
        "updatedAt":             rec.get("updatedAt"),
        "creator_name":          rec.get("creator_name"),
        "creator_email":         rec.get("creator_email"),
        "updator_name":          rec.get("updator_name"),
        "updator_email":         rec.get("updator_email"),
        "bookmark_count":        rec.get("bookmark_count", 0),
        "summary_text":          summary.get("text"),
        "summary_image_url":     summary.get("image_url"),
        "image_description":     summary.get("image_description"),
        "credits":               rec.get("credits"),
        "projects":              rec.get("projects"),
        "palette_projects":      rec.get("palette_projects"),
        "team":                  rec.get("team"),
        "related_cards":         rec.get("related_cards"),
        "resources":             rec.get("resources"),
        "palette_mk_links":      rec.get("palette_mk_links"),
    }
    return {
        "_id":         rec["id"],
        "type":        "card",
        "paletteId":   None,
        "title":       rec.get("name") or "",
        "text":        _card_text(rec),
        "metadata":    metadata,
        "vector_field": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PDF download + chunk
# ─────────────────────────────────────────────────────────────────────────────

def _is_pdf(data: bytes) -> bool:
    return len(data) >= 5 and data[:4] == b"%PDF"


def _chunk_text(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        window = text[start:end]
        for sep in ("\n", ". ", ".\n", "? ", "! "):
            idx = window.rfind(sep)
            if idx > CHUNK_SIZE // 2:
                end = start + idx + len(sep)
                break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP
    return chunks


def _pdf_chunk_doc(resource_id: str, palette_id: str, title: str,
                   idx: int, total: int, content: str, link: str = None) -> Dict:
    chunk_id = f"{resource_id}_{idx}" if total > 1 else resource_id
    metadata = {
        "id":           chunk_id,
        "resource_id":  resource_id,
        "paletteId":    palette_id,
        "title":        title,
        "chunk_index":  idx,
        "total_chunks": total,
        "fileType":     "pdf",
        "link":         link,
    }
    text = (
        f"# {title or 'PDF Document'}\n"
        f"Palette Card ID: {palette_id}\n"
        f"Chunk: {idx + 1} / {total}\n\n"
        f"{content}"
    )
    return {
        "_id":           chunk_id,
        "type":          "pdf_chunk",
        "paletteId":     palette_id,
        "title":         title or "",
        "text":          text.strip(),
        "metadata":      metadata,
        "vector_field":  [],
    }


async def _download(session: aiohttp.ClientSession, url: str, headers: Dict) -> bytes:
    try:
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                return b""
            body = await r.read()
            ct = (r.headers.get("Content-Type") or "").lower()
            if "text/html" in ct:
                return b""
            return body
    except Exception as exc:
        log.debug("Download failed %s: %s", url, exc)
        return b""


async def _process_pdf(
    entry: Dict,
    session: aiohttp.ClientSession,
    hub_headers: Dict,
    sem: asyncio.Semaphore,
    idx: int,
    total: int,
) -> List[Dict]:
    async with sem:
        fid   = entry.get("fileId") or ""
        url   = entry.get("pdf_url") or ""
        rid   = entry.get("_id") or ""
        pid   = entry.get("paletteId") or ""
        title = entry.get("title") or ""

        if fid:
            data = await _download(session, f"{cfg.HUB_FILE_DOWNLOAD_URL}/{fid}", hub_headers)
        elif url:
            h = hub_headers if "hub.perkinswill.com" in url else {}
            data = await _download(session, url, h)
        else:
            return []

        if not _is_pdf(data):
            log.debug("[%d/%d] Not a PDF: %s", idx + 1, total, fid or url)
            return []

        try:
            doc   = fitz.open(stream=data, filetype="pdf")
            text  = "\n".join(p.get_text() for p in doc).strip()
            doc.close()
        except Exception as exc:
            log.warning("[%d/%d] PDF extract error %s: %s", idx + 1, total, fid or url, exc)
            return []

        if not text:
            return []

        chunks = _chunk_text(text)
        log.info("[%d/%d] %d chunks from: %s", idx + 1, total, len(chunks), title or fid or url)
        return [_pdf_chunk_doc(rid, pid, title, i, len(chunks), c, url or None)
                for i, c in enumerate(chunks)]


async def process_pdfs(pdf_candidates: List[Dict]) -> List[Dict]:
    from src.hub_token_access.get_auth_token import get_hub_headers
    hub_headers = get_hub_headers()
    sem   = asyncio.Semaphore(cfg.PDF_CONCURRENCY)
    total = len(pdf_candidates)
    results: List[Dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = [
            _process_pdf(e, session, hub_headers, sem, i, total)
            for i, e in enumerate(pdf_candidates)
        ]
        for coro in asyncio.as_completed(tasks):
            try:
                chunks = await coro
                results.extend(chunks)
            except Exception as exc:
                log.error("PDF processing error: %s", exc)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Splashscreen docs
# ─────────────────────────────────────────────────────────────────────────────

def splashscreen_to_doc(rec: Dict) -> Dict:
    text  = f"# {rec.get('title','Splash Screen')}\n{rec.get('content','')}"
    return {
        "_id":         rec["_id"],
        "type":        "splashscreen",
        "paletteId":   None,
        "title":       rec.get("title") or "Splash Screen",
        "text":        text.strip(),
        "metadata":    rec,
        "vector_field": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run(input_path: str, output_path: str, skip_pdfs: bool):
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    cards          = data.get("cards") or []
    pdf_candidates = data.get("pdf_candidates") or []
    splashscreens  = data.get("splashscreen") or []

    log.info("Building card docs (%d cards) ...", len(cards))
    all_docs: List[Dict] = [card_to_doc(c) for c in cards]

    log.info("Building splashscreen docs (%d) ...", len(splashscreens))
    all_docs.extend(splashscreen_to_doc(s) for s in splashscreens)

    if not skip_pdfs:
        log.info("Processing %d PDF candidates ...", len(pdf_candidates))
        pdf_docs = await process_pdfs(pdf_candidates)
        all_docs.extend(pdf_docs)
        log.info("  → %d PDF chunk docs", len(pdf_docs))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, indent=2, ensure_ascii=False)

    # Summary
    by_type: Dict[str, int] = {}
    for d in all_docs:
        by_type[d["type"]] = by_type.get(d["type"], 0) + 1

    log.info("✓ %d total docs → %s", len(all_docs), output_path)
    for t, n in sorted(by_type.items()):
        log.info("    %s: %d", t, n)


def main():
    ap = argparse.ArgumentParser(description="Chunk extracted Palette data into index documents")
    ap.add_argument("--input",    default=INPUT_FILE,  help=f"Input JSON (default: {INPUT_FILE})")
    ap.add_argument("--output",   default=OUTPUT_FILE, help=f"Output JSON (default: {OUTPUT_FILE})")
    ap.add_argument("--no-pdfs",  action="store_true", help="Skip PDF download and chunking")
    args = ap.parse_args()
    asyncio.run(run(args.input, args.output, args.no_pdfs))


if __name__ == "__main__":
    main()