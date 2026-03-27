"""
Count PDFs from output_index.json by inspecting resources in each doc's metadata.

Strategy:
- PDF by fileType: resource.fileType == "pdf"
- PDF by URL: resource has link and ".pdf" in link (case-insensitive)
- PDF by fileId: resource has fileId (Hub file). Type is not in Mongo; use --hub to
  resolve via Hub API (HEAD/GET first bytes and check Content-Type or %PDF magic).

Usage:
  python count_pdfs_in_output_index.py           # index-only counts
  python count_pdfs_in_output_index.py --hub    # also resolve fileIds via Hub API

Requires .env with HUB_FILE_DOWNLOAD_URL and HUB_CLIENT_ID / HUB_CLIENT_SECRET (or HUB_AUTH_COOKIE) when using --hub.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow importing src.config when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUTPUT_INDEX_JSON = "output_index.json"
HUB_CHECK_CONCURRENCY = 5
HUB_CHECK_TIMEOUT = 30
HUB_READ_BYTES = 512


def is_pdf_by_url(link) -> bool:
    if not link or not isinstance(link, str):
        return False
    return ".pdf" in link.lower()


def collect_resources_from_index(path: str) -> list:
    """Yield (resource_id, fileType, link, fileId) from every doc that has metadata.resources."""
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    if not isinstance(docs, list):
        docs = [docs]
    for doc in docs:
        meta = doc.get("metadata") or {}
        resources = meta.get("resources") or []
        for r in resources:
            rid = r.get("_id")
            if not rid:
                continue
            yield (
                rid,
                (r.get("fileType") or "").strip().lower(),
                r.get("link"),
                r.get("fileId"),
            )


async def _is_pdf_from_hub(session, url: str, headers: dict, semaphore) -> bool:
    """Request first bytes from Hub and return True if PDF (Content-Type or %PDF magic)."""
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=HUB_CHECK_TIMEOUT)
    async with semaphore:
        try:
            h = {**headers, "Range": f"bytes=0-{HUB_READ_BYTES - 1}"}
            async with session.get(url, headers=h, timeout=timeout) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                if "application/pdf" in ct:
                    return True
                # Some servers ignore Range and return 200 with full body; read only what we need
                body = b""
                async for chunk in resp.content.iter_chunked(1024):
                    body += chunk
                    if len(body) >= 5:
                        break
                return len(body) >= 5 and body[:4] == b"%PDF"
        except Exception:
            return False


def _load_hub_base():
    """Load Hub download base URL from config or .env."""
    try:
        from src.config import HUB_FILE_DOWNLOAD_URL
        return (HUB_FILE_DOWNLOAD_URL or "").strip() or "https://files.hub.perkinswill.com/download"
    except ImportError:
        pass
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent / ".env")
    except Exception:
        pass
    return (os.getenv("HUB_FILE_DOWNLOAD_URL") or "").strip() or "https://files.hub.perkinswill.com/download"


async def resolve_fileids_via_hub(file_ids) -> set:
    """Return set of fileIds that are PDFs according to Hub (first bytes or Content-Type). Uses OAuth2 token or cookie."""
    from src.hub_token_access.get_auth_token import get_hub_headers
    base = _load_hub_base()
    base = (base or "").rstrip("/") or "https://files.hub.perkinswill.com/download"
    headers = get_hub_headers()
    if not headers:
        print("Warning: No Hub auth (set HUB_CLIENT_ID and HUB_CLIENT_SECRET, or HUB_AUTH_COOKIE); Hub may return 401.", file=sys.stderr)

    ids_list = list(file_ids)  # stable order for matching results
    semaphore = asyncio.Semaphore(HUB_CHECK_CONCURRENCY)
    pdf_file_ids = set()

    import aiohttp
    async with aiohttp.ClientSession() as session:
        tasks = [
            _is_pdf_from_hub(session, f"{base}/{fid}", headers, semaphore)
            for fid in ids_list
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for fid, result in zip(ids_list, results):
            if result is True:
                pdf_file_ids.add(fid)
            if isinstance(result, Exception):
                pass  # treat as not PDF

    return pdf_file_ids


def main():
    parser = argparse.ArgumentParser(description="Count PDFs in output_index.json (optionally resolve Hub fileIds).")
    parser.add_argument("--hub", action="store_true", help="Resolve fileIds via Hub API to count PDFs (needs HUB_FILE_DOWNLOAD_URL, HUB_AUTH_COOKIE)")
    args = parser.parse_args()

    path = Path(OUTPUT_INDEX_JSON)
    if not path.exists():
        print(f"{OUTPUT_INDEX_JSON} not found.", file=sys.stderr)
        sys.exit(1)

    seen = set()
    pdf_by_filetype = set()
    pdf_by_url = set()
    with_fileid = set()
    total_resource_entries = 0
    # rid -> fileId for resources that have fileId (one-to-one per rid in our data)
    rid_to_fileid = {}

    for rid, file_type, link, file_id in collect_resources_from_index(str(path)):
        total_resource_entries += 1
        if rid in seen:
            continue
        seen.add(rid)

        if file_type == "pdf":
            pdf_by_filetype.add(rid)
        if is_pdf_by_url(link):
            pdf_by_url.add(rid)
        if file_id:
            with_fileid.add(rid)
            rid_to_fileid[rid] = file_id

    # Unique PDFs: by fileType OR by URL (union)
    pdfs_certain = pdf_by_filetype | pdf_by_url
    # Resources with fileId but not already counted as PDF
    with_fileid_not_pdf = with_fileid - pdfs_certain
    # Unique fileIds to resolve via Hub (only those not already known PDF)
    fileids_to_resolve = {rid_to_fileid[rid] for rid in with_fileid_not_pdf}

    pdf_by_hub = set()
    if args.hub and fileids_to_resolve:
        print(f"Resolving {len(fileids_to_resolve)} fileIds via Hub API...", file=sys.stderr)
        pdf_file_ids = asyncio.run(resolve_fileids_via_hub(fileids_to_resolve))
        # Resource _ids whose fileId is PDF according to Hub
        pdf_by_hub = {rid for rid, fid in rid_to_fileid.items() if fid in pdf_file_ids}

    print(f"From {OUTPUT_INDEX_JSON} (metadata.resources in palette docs):")
    print(f"  Total resource entries: {total_resource_entries}")
    print(f"  Unique resource IDs:   {len(seen)}")
    print()
    print("PDFs (unique by resource _id):")
    print(f"  By fileType == 'pdf':  {len(pdf_by_filetype)}")
    print(f"  By URL (.pdf in link): {len(pdf_by_url)}")
    if args.hub:
        print(f"  By Hub API (fileId):   {len(pdf_by_hub)}")
    print(f"  Total unique PDFs (fileType or URL): {len(pdfs_certain)}")
    if args.hub:
        total_pdfs = pdfs_certain | pdf_by_hub
        print(f"  Total unique PDFs (incl. Hub):     {len(total_pdfs)}")
    print()
    print("Hub files (have fileId; type unknown from index):")
    print(f"  With fileId:           {len(with_fileid)}")
    print(f"  With fileId, not already PDF: {len(with_fileid_not_pdf)} (may be PDFs if extension not set)")
    if args.hub:
        print(f"  → Resolved as PDF via Hub:        {len(pdf_by_hub)}")
    print()
    print(f"  → Total PDFs (certain, index only): {len(pdfs_certain)}")
    if args.hub:
        print(f"  → Total PDFs (with Hub resolve):  {len(pdfs_certain | pdf_by_hub)}")
    else:
        print(f"  → If all fileId-not-PDF are PDFs: {len(pdfs_certain) + len(with_fileid_not_pdf)} (upper bound)")
        print(f"  → Run with --hub to resolve fileIds via Hub API for exact PDF count.")


if __name__ == "__main__":
    main()
