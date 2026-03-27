"""
Categorize resources with fileType "others" by downloading/HEAD and checking Content-Type or magic bytes.

Usage:
  python categorize_others.py                    # from output_index.json, Hub fileIds only
  python categorize_others.py --with-links       # also probe links (may get 403 for SharePoint)
  python categorize_others.py --output types.json # write resource_id -> type to JSON

Requires: .env with HUB_FILE_DOWNLOAD_URL and HUB_CLIENT_ID / HUB_CLIENT_SECRET (or HUB_AUTH_COOKIE) for Hub fileIds.
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aiohttp

from src.config import HUB_FILE_DOWNLOAD_URL
from src.hub_token_access.get_auth_token import get_hub_headers

OUTPUT_INDEX_JSON = "output_index.json"
READ_BYTES = 8192  # enough for ZIP central dir / OLE header
CONCURRENCY = 5
TIMEOUT = 25

# Content-Type (lower) -> category
CT_TO_TYPE = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/msexcel": "xls",
    "application/zip": "zip",
    "text/plain": "txt",
    "text/html": "html",
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
}

# List of Content-Type strings we currently map (for reference / adding new ones from probe runs)
KNOWN_CONTENT_TYPES = list(CT_TO_TYPE.keys())

# Magic bytes -> category (only when Content-Type is missing or generic)
def _magic_type(first_bytes: bytes) -> str:
    if not first_bytes or len(first_bytes) < 4:
        return "unknown"
    if first_bytes[:4] == b"%PDF":
        return "pdf"
    if first_bytes[:2] == b"PK":
        # ZIP: docx, pptx, xlsx - peek inside
        if b"word/document" in first_bytes or b"word\\document" in first_bytes:
            return "docx"
        if b"ppt/presentation" in first_bytes or b"ppt\\presentation" in first_bytes:
            return "pptx"
        if b"xl/workbook" in first_bytes or b"xl\\workbook" in first_bytes:
            return "xlsx"
        return "zip"
    if len(first_bytes) >= 8 and first_bytes[:8] == bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]):
        # OLE: could be doc, ppt, xls - heuristic from stream names later would be needed; treat as legacy office
        return "ole_office"
    return "unknown"


def _is_card(doc: dict) -> bool:
    meta = doc.get("metadata") or {}
    return isinstance(meta.get("resources"), list)


def collect_others_resources(path: str, with_links: bool) -> list:
    """List of { resource_id, palette_id, fileId, link, title } for fileType 'others'."""
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    if not isinstance(docs, list):
        docs = [docs]
    out = []
    seen = set()
    for doc in docs:
        if not _is_card(doc):
            continue
        meta = doc.get("metadata") or {}
        pid = meta.get("id") or doc.get("_id")
        title = (meta.get("title") or doc.get("title") or "").strip()
        for r in meta.get("resources") or []:
            ft = (r.get("fileType") or "").strip().lower()
            if ft != "others":
                continue
            rid = r.get("_id")
            if not rid or rid in seen:
                continue
            link = r.get("link") if isinstance(r.get("link"), str) else None
            fid = r.get("fileId")
            if not fid and not (with_links and link):
                continue
            seen.add(rid)
            out.append({
                "_id": rid,
                "paletteId": pid,
                "fileId": fid,
                "link": link,
                "title": title,
            })
    return out


async def probe_hub(session: aiohttp.ClientSession, file_id: str, semaphore) -> tuple:
    """Return (content_type_from_header, first_bytes, status). Uses Range request and OAuth2 token."""
    base = (HUB_FILE_DOWNLOAD_URL or "").rstrip("/") or "https://files.hub.perkinswill.com/download"
    url = f"{base}/{file_id}"
    headers = get_hub_headers()
    async with semaphore:
        try:
            h = {**headers, "Range": f"bytes=0-{READ_BYTES - 1}"}
            async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
                ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                body = b""
                async for chunk in resp.content.iter_chunked(4096):
                    body += chunk
                    if len(body) >= READ_BYTES:
                        break
                return ct, body, resp.status
        except Exception as e:
            return "", b"", 0


async def probe_link(session: aiohttp.ClientSession, link: str, semaphore) -> tuple:
    """Return (content_type_from_header, first_bytes, status)."""
    async with semaphore:
        try:
            headers = {"Range": f"bytes=0-{READ_BYTES - 1}"}
            async with session.get(link, headers=headers, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
                ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                body = b""
                async for chunk in resp.content.iter_chunked(4096):
                    body += chunk
                    if len(body) >= READ_BYTES:
                        break
                return ct, body, resp.status
        except Exception:
            return "", b"", 0


def resolve_type(content_type: str, first_bytes: bytes, status: int = 200) -> str:
    """Decide category from status, Content-Type and magic bytes."""
    if status == 401:
        return "auth_required"
    if status == 403:
        return "forbidden"
    if status and status != 200:
        return "error"
    # Ignore JSON/HTML error bodies
    ct_lower = (content_type or "").strip().lower()
    if "application/json" in ct_lower or "text/html" in ct_lower:
        if first_bytes[:4] == b"%PDF":
            return "pdf"
        if first_bytes[:2] == b"PK":
            return _magic_type(first_bytes)
        return "unknown_response"
    for ct, cat in CT_TO_TYPE.items():
        if ct in ct_lower or ct_lower in ct:
            return cat
    return _magic_type(first_bytes)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Categorize 'others' resources by downloading/probing")
    parser.add_argument("--with-links", action="store_true", help="Also probe resources that have link (no fileId)")
    parser.add_argument("--output", metavar="FILE", help="Write resource_id -> type mapping JSON")
    args = parser.parse_args()

    path = Path(OUTPUT_INDEX_JSON)
    if not path.exists():
        print(OUTPUT_INDEX_JSON, "not found", file=sys.stderr)
        sys.exit(1)

    resources = collect_others_resources(str(path), with_links=args.with_links)
    print(f"Found {len(resources)} resources with fileType 'others' to probe (fileId or link).")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = {}  # resource_id -> resolved_type
    by_type = {}
    content_types_seen = set()  # raw Content-Type headers from responses (to find missing CT_TO_TYPE entries)

    async with aiohttp.ClientSession() as session:
        for i, r in enumerate(resources):
            rid, fid, link = r["_id"], r.get("fileId"), r.get("link")
            status = 200
            if fid:
                ct, body, status = await probe_hub(session, fid, semaphore)
            elif link:
                ct, body, status = await probe_link(session, link, semaphore)
            else:
                continue
            if ct:
                content_types_seen.add(ct.strip().lower())
            resolved = resolve_type(ct, body, status)
            results[rid] = resolved
            by_type[resolved] = by_type.get(resolved, 0) + 1
            if (i + 1) % 50 == 0 or i == len(resources) - 1:
                print(f"  Probed {i + 1}/{len(resources)} ...")

    print()
    print("=== Resolved file types (from 'others') ===")
    for t in sorted(by_type.keys(), key=lambda x: -by_type[x]):
        print(f"  {t}: {by_type[t]}")
    print(f"  Total: {sum(by_type.values())}")

    # Content-Types seen but not in CT_TO_TYPE (add these to CT_TO_TYPE to reduce "unknown")
    known_set = set(CT_TO_TYPE.keys())
    missing_ct = sorted(content_types_seen - known_set)
    if missing_ct:
        print()
        print("=== Content-Types seen that are NOT in CT_TO_TYPE (add to CT_TO_TYPE to recognize them) ===")
        for ct in missing_ct:
            print(f"  {ct!r}")
        missing_path = Path("content_types_to_add.json")
        with open(missing_path, "w", encoding="utf-8") as f:
            json.dump(missing_ct, f, indent=2)
        print(f"  Wrote list to {missing_path}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Wrote {len(results)} mappings to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
