"""
Fetch PDFs from card docs (in-memory or from file for debug): (1) direct PDF URLs,
(2) Hub fileIds resolved as PDF. Get PDF bytes, POST to parser API, chunk markdown.
All processing is in memory; output_index.json is for debugging only.

In-memory API (for pipeline):
  from run_pdf_parser_to_index import process_pdfs_into_chunks
  new_chunks = await process_pdfs_into_chunks(index_docs)  # returns list of chunk docs

CLI (standalone / debug):
  python run_pdf_parser_to_index.py              # in-memory; load from file, no write
  python run_pdf_parser_to_index.py --debug-dump # write to output_index.json for debug
  python run_pdf_parser_to_index.py --legacy     # use PDF_URLs + MICROFILES from Mongo

Requires: PDF parser at PDF_PARSER_API_URL (default http://localhost:8000).
"""
import asyncio
import json
import os
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aiohttp

from src.config import (
    PDF_PARSER_API_URL,
    PDF_PARSER_FILE_FIELD,
    HUB_FILE_DOWNLOAD_URL,
    MICROFILES,
)
from src.hub_token_access.get_auth_token import get_hub_headers
from src.process.pdf_chunks import chunk_text, build_chunk_doc

OUTPUT_INDEX_JSON = "output_index.json"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
TIMEOUT = 500
HUB_RESOLVE_CONCURRENCY = 5
HUB_RESOLVE_TIMEOUT = 30
HUB_READ_BYTES = 512
# Process one PDF at a time (no concurrent sends to API)

# Default direct PDF URLs when using --legacy and PDF_URLs env is not set
DEFAULT_PDF_URLS = [
    "https://www.lifecyclebuilding.org/docs/DfDseattle.pdf",
]


async def download_pdf_from_hub(session: aiohttp.ClientSession, file_id: str) -> bytes:
    """Download full PDF from Hub by fileId. Uses OAuth2 token (HUB_CLIENT_ID/SECRET) or HUB_AUTH_COOKIE.
    Returns raw PDF bytes only (validated by %PDF magic)."""
    base = (HUB_FILE_DOWNLOAD_URL or "").rstrip("/") or "https://files.hub.perkinswill.com/download"
    url = f"{base}/{file_id}"
    headers = get_hub_headers()
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
        if resp.status != 200:
            return b""
        body = await resp.read()
        if len(body) < 5 or body[:4] != b"%PDF":
            return b""
        return body  # raw PDF bytes, sent as PDF to API


async def download_pdf_from_url(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
        if resp.status != 200:
            return b""
        body = await resp.read()
        if len(body) < 5 or body[:4] != b"%PDF":
            return b""
        return body


async def parse_pdf_via_api(
    session: aiohttp.ClientSession,
    pdf_bytes: bytes,
    api_base: str,
    log_empty_reason: bool = True,
) -> str:
    """POST PDF to API /extract (API accepts only PDF). Returns markdown."""
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        if log_empty_reason:
            print(f"    -> Parser skipped: invalid PDF bytes (len={len(pdf_bytes) if pdf_bytes else 0})")
        return ""
    api_url = f"{api_base.rstrip('/')}/extract"
    data = aiohttp.FormData()
    # Send as PDF: raw bytes, application/pdf (same for direct URLs and Hub-resolved PDFs)
    data.add_field(
        PDF_PARSER_FILE_FIELD,
        BytesIO(pdf_bytes),
        filename="document.pdf",
        content_type="application/pdf",
    )
    try:
        async with session.post(api_url, data=data, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
            text = (await resp.text()).strip()
            if resp.status != 200:
                if log_empty_reason:
                    preview = (text or resp.reason or "no body")[:400]
                    print(f"    -> Parser returned HTTP {resp.status}: {preview}")
                return ""
            if not text and log_empty_reason:
                print(f"    -> Parser returned HTTP 200 but empty body (no markdown)")
            return text
    except asyncio.TimeoutError:
        if log_empty_reason:
            print(f"    -> Parser request timed out after {TIMEOUT}s")
        return ""
    except Exception as e:
        if log_empty_reason:
            print(f"    -> Parser request failed: {type(e).__name__}: {e}")
        return ""


def markdown_to_chunk_docs(
    markdown: str,
    resource_id: str,
    palette_id: str,
    title: str,
    link: str = None,
) -> list:
    """Chunk markdown and return list of chunk docs (same shape as pdf_chunks)."""
    if not markdown or not markdown.strip():
        return []
    chunks = chunk_text(markdown, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    out = []
    for i, exact in enumerate(chunks):
        doc = build_chunk_doc(
            resource_id=resource_id,
            palette_id=palette_id,
            title=title,
            chunk_index=i,
            total_chunks=len(chunks),
            exact_content=exact,
            link=link,
        )
        out.append(doc)
    return out


def _is_doc_card(doc: dict) -> bool:
    """True if doc is a palette card (has metadata.resources), not a chunk doc."""
    meta = doc.get("metadata") or {}
    return isinstance(meta.get("resources"), list)


def load_pdf_sources_from_docs(docs: list) -> tuple:
    """
    Extract PDF sources from an in-memory list of index docs (card docs only).
    Returns (url_sources, hub_sources). Deduped by resource _id.
    - url_sources: list of { source: "url", _id, paletteId, url, title }
    - hub_sources: list of { source: "hub", _id, paletteId, fileId, title }
    """
    if not isinstance(docs, list):
        docs = [docs] if docs else []
    seen_rid = set()
    url_sources = []
    hub_sources = []
    for doc in docs:
        if not _is_doc_card(doc):
            continue
        meta = doc.get("metadata") or {}
        palette_id = (meta.get("id") or doc.get("_id") or "").strip()
        card_title = (meta.get("title") or doc.get("title") or "").strip()
        for r in meta.get("resources") or []:
            rid = r.get("_id")
            if not rid or rid in seen_rid:
                continue
            link = r.get("link")
            file_id = r.get("fileId")
            if link and isinstance(link, str) and ".pdf" in link.lower():
                seen_rid.add(rid)
                url_sources.append({
                    "source": "url",
                    "_id": rid,
                    "paletteId": palette_id,
                    "url": link,
                    "title": card_title or "PDF",
                })
            elif file_id:
                seen_rid.add(rid)
                hub_sources.append({
                    "source": "hub",
                    "_id": rid,
                    "paletteId": palette_id,
                    "fileId": str(file_id).strip(),
                    "title": card_title or "PDF",
                })
    return url_sources, hub_sources


def load_pdf_sources_from_index(index_path: str) -> tuple:
    """
    Load PDF sources from a JSON file (debug only). Delegates to load_pdf_sources_from_docs after reading file.
    """
    path = Path(index_path)
    if not path.exists():
        return [], []
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    return load_pdf_sources_from_docs(docs)


async def _hub_is_pdf(session: aiohttp.ClientSession, url: str, headers: dict, semaphore) -> bool:
    """Request first bytes from Hub; return True if Content-Type application/pdf or %PDF magic."""
    async with semaphore:
        try:
            h = {**headers, "Range": f"bytes=0-{HUB_READ_BYTES - 1}"}
            async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=HUB_RESOLVE_TIMEOUT)) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                if "application/pdf" in ct:
                    return True
                body = b""
                async for chunk in resp.content.iter_chunked(1024):
                    body += chunk
                    if len(body) >= 5:
                        break
                return len(body) >= 5 and body[:4] == b"%PDF"
        except Exception:
            return False


async def resolve_hub_pdf_fileids(hub_sources: list) -> list:
    """Filter hub_sources to only entries whose fileId is PDF according to Hub (Range request)."""
    if not hub_sources:
        return []
    base = (HUB_FILE_DOWNLOAD_URL or "").rstrip("/") or "https://files.hub.perkinswill.com/download"
    headers = get_hub_headers()
    fileid_to_sources = {}
    for s in hub_sources:
        fid = s["fileId"]
        fileid_to_sources.setdefault(fid, []).append(s)
    ids_list = list(fileid_to_sources.keys())
    semaphore = asyncio.Semaphore(HUB_RESOLVE_CONCURRENCY)
    pdf_file_ids = set()
    async with aiohttp.ClientSession() as session:
        tasks = [_hub_is_pdf(session, f"{base}/{fid}", headers, semaphore) for fid in ids_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for fid, ok in zip(ids_list, results):
            if ok is True:
                pdf_file_ids.add(fid)
    out = []
    seen_rid = set()
    for s in hub_sources:
        if s["fileId"] in pdf_file_ids and s["_id"] not in seen_rid:
            seen_rid.add(s["_id"])
            out.append(s)
    return out


async def get_pdf_sources_from_microfiles() -> list:
    """List of { _id, paletteId, fileId, title } for MICROFILES entries that have fileId. PDF check done after download."""
    if not MICROFILES:
        return []
    from src.db_connections.db import MongoService
    db = MongoService()
    all_files = await db.get_all_records(MICROFILES, {})
    out = []
    for f in all_files:
        file_id = f.get("fileId") or f.get("file_id")
        if not file_id:
            continue
        out.append({
            "source": "microfiles",
            "_id": str(f.get("_id")) if f.get("_id") else None,
            "paletteId": str(f.get("paletteId")) if f.get("paletteId") else None,
            "fileId": str(file_id),
            "title": (f.get("title") or f.get("name") or "").strip(),
            "link": f.get("link"),
        })
    return out


def get_pdf_sources_from_urls() -> list:
    """Direct PDF URLs from env PDF_URLs (comma-separated), or DEFAULT_PDF_URLs if unset."""
    urls_str = os.getenv("PDF_URLs", "").strip()
    if urls_str:
        urls = [u.strip() for u in urls_str.split(",") if u.strip()]
    else:
        urls = list(DEFAULT_PDF_URLS)
    out = []
    for url in urls:
        if not url.startswith("http"):
            continue
        if not url.lower().endswith(".pdf"):
            continue
        out.append({
            "source": "url",
            "_id": f"url_{abs(hash(url)) % 10**10}",
            "paletteId": "url",
            "url": url,
            "title": url.split("/")[-1].split("?")[0] or "PDF",
        })
    return out


def _link_for_source(src: dict) -> str:
    if src.get("source") == "url":
        return src.get("url") or ""
    return src.get("link") or src.get("url") or ""


async def _process_one_pdf(
    session: aiohttp.ClientSession,
    src: dict,
    index: int,
    total: int,
    api_base: str,
) -> list:
    """Download PDF bytes (from URL or Hub). Hub-resolved PDFs are sent to the API as PDF (raw bytes, application/pdf).
    Runs one PDF at a time (blocking style)."""
    if src["source"] == "url":
        pdf_bytes = await download_pdf_from_url(session, src["url"])
    else:
        # Hub: full PDF download; bytes sent as PDF to API (no conversion)
        pdf_bytes = await download_pdf_from_hub(session, src["fileId"])
    if not pdf_bytes:
        print(f"  [{index + 1}/{total}] Skip (no PDF): {src.get('title') or src.get('fileId') or src.get('url', '')}")
        return []
    print(f"  [{index + 1}/{total}] Parsing: {src.get('title') or src.get('fileId') or src.get('url', '')}")
    # API accepts only PDF: we send pdf_bytes as multipart file with content_type=application/pdf
    markdown = await parse_pdf_via_api(session, pdf_bytes, api_base, log_empty_reason=True)
    if not markdown:
        return []
    rid = src.get("_id") or f"doc_{index}"
    pid = src.get("paletteId") or "unknown"
    title = src.get("title") or "PDF"
    link = _link_for_source(src)
    return markdown_to_chunk_docs(markdown, rid, pid, title, link)


async def process_pdfs_into_chunks(
    index_docs: list,
    api_base: str = None,
    use_legacy: bool = False,
) -> list:
    """
    In-memory only: get PDF sources from card docs in index_docs, fetch markdown from parser API,
    chunk, and return list of new chunk docs. No file I/O.
    index_docs: list of index documents (card docs with metadata.resources; chunk docs are ignored).
    Returns: list of new chunk documents to append to index.
    """
    api_base = api_base or PDF_PARSER_API_URL or "http://localhost:8000"
    card_docs = [d for d in index_docs if _is_doc_card(d)]
    if use_legacy:
        url_sources = get_pdf_sources_from_urls()
        mf_sources = await get_pdf_sources_from_microfiles()
        all_sources = url_sources + mf_sources
    else:
        url_sources, hub_sources = load_pdf_sources_from_docs(card_docs)
        resolved_hub = await resolve_hub_pdf_fileids(hub_sources)
        all_sources = url_sources + resolved_hub
    if not all_sources:
        return []
    new_chunks = []
    total_sources = len(all_sources)
    async with aiohttp.ClientSession() as session:
        for i, src in enumerate(all_sources):
            try:
                chunks = await _process_one_pdf(session, src, i, total_sources, api_base)
                new_chunks.extend(chunks)
            except Exception:
                pass
    return new_chunks


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch PDFs, send to parser API; in-memory by default. Use --debug-dump to write output_index.json.")
    parser.add_argument("--legacy", action="store_true", help="Use PDF_URLs env + MICROFILES from Mongo")
    parser.add_argument("--from-file", default=OUTPUT_INDEX_JSON, metavar="PATH", help=f"Load card docs from file (debug). Default: {OUTPUT_INDEX_JSON}")
    parser.add_argument("--debug-dump", action="store_true", help="Write result to output_index.json (debug only; default is in-memory only)")
    args = parser.parse_args()

    api_base = PDF_PARSER_API_URL or "http://localhost:8000"
    print("PDF parser API:", api_base)

    # Load sources: from file only when running standalone (for debug)
    if args.legacy:
        url_sources = get_pdf_sources_from_urls()
        mf_sources = await get_pdf_sources_from_microfiles()
        all_sources = url_sources + mf_sources
        print("Sources (legacy):", len(url_sources), "URLs,", len(mf_sources), "MICROFILES")
    else:
        url_sources, hub_sources = load_pdf_sources_from_index(args.from_file)
        print("From file: direct PDF URLs:", len(url_sources), ", Hub candidates:", len(hub_sources))
        resolved_hub = await resolve_hub_pdf_fileids(hub_sources)
        all_sources = url_sources + resolved_hub
        print("Total PDFs to process:", len(all_sources))

    if not all_sources:
        print("No PDF sources. Exiting.")
        return

    new_chunks = []
    total_sources = len(all_sources)
    async with aiohttp.ClientSession() as session:
        for i, src in enumerate(all_sources):
            try:
                chunks = await _process_one_pdf(session, src, i, total_sources, api_base)
                new_chunks.extend(chunks)
            except Exception as e:
                print("    -> Error:", e)

    seen_rid = set()
    for c in new_chunks:
        rid = c.get("metadata", {}).get("resource_id")
        if rid:
            seen_rid.add(rid)
    pdfs_processed = len(seen_rid)
    print("Processed", pdfs_processed, "PDFs,", len(new_chunks), "chunks (in memory).")

    if not new_chunks:
        return

    if args.debug_dump:
        path = Path(OUTPUT_INDEX_JSON)
        existing = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.extend(new_chunks)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str, ensure_ascii=False)
        print("Debug: written", len(existing), "docs to", OUTPUT_INDEX_JSON)


if __name__ == "__main__":
    asyncio.run(main())
