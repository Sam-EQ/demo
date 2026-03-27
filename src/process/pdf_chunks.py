"""
PDF text extraction and chunking for resources with fileType pdf.
Produces chunk documents: { _id, paletteId, exact_content, search_content, text }
with text = markdown containing embedded JSON metadata and content.

Hub file download uses OAuth2 token (HUB_CLIENT_ID/SECRET) or HUB_AUTH_COOKIE via get_hub_headers().
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional

import aiohttp
import fitz  # pymupdf

# Chunk size in characters; overlap for context across chunks
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
PDF_DOWNLOAD_TIMEOUT = 60
PDF_DOWNLOAD_CONNECT_TIMEOUT = 15

_log = logging.getLogger(__name__)


def _get_hub_headers() -> Dict[str, str]:
    """Hub auth: OAuth2 token or cookie."""
    try:
        from src.hub_token_access.get_auth_token import get_hub_headers
        return get_hub_headers()
    except Exception:
        return {}


def _is_pdf_bytes(data: bytes) -> bool:
    """True if bytes look like a PDF (magic header)."""
    return len(data) >= 5 and data[:4] == b"%PDF"


async def download_pdf(
    session: aiohttp.ClientSession,
    file_id: str,
    download_base: str,
    auth_headers: Optional[Dict[str, str]] = None,
) -> bytes:
    """Download full PDF from Hub. Uses auth_headers from get_hub_headers() if not provided."""
    base = download_base.rstrip("/")
    url = f"{base}/{file_id}"
    headers = auth_headers if auth_headers is not None else _get_hub_headers()
    try:
        timeout = aiohttp.ClientTimeout(total=PDF_DOWNLOAD_TIMEOUT, connect=PDF_DOWNLOAD_CONNECT_TIMEOUT)
        async with session.get(url, headers=headers, timeout=timeout) as resp:
            if resp.status != 200:
                return b""
            body = await resp.read()
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" in ct or (body[:500] and b"<html" in body[:500].lower()):
                return b""
            return body
    except Exception:
        return b""


async def download_pdf_from_url(
    session: aiohttp.ClientSession,
    url: str,
    auth_headers: Optional[Dict[str, str]] = None,
) -> bytes:
    """Download PDF from arbitrary URL. For Hub URLs uses get_hub_headers() if auth_headers not provided."""
    headers = {}
    if "hub.perkinswill.com" in url:
        headers = auth_headers if auth_headers is not None else _get_hub_headers()
    try:
        timeout = aiohttp.ClientTimeout(total=PDF_DOWNLOAD_TIMEOUT, connect=PDF_DOWNLOAD_CONNECT_TIMEOUT)
        async with session.get(url, headers=headers or None, timeout=timeout) as resp:
            if resp.status != 200:
                return b""
            body = await resp.read()
            if not _is_pdf_bytes(body):
                ct = (resp.headers.get("Content-Type") or "").lower()
                if "application/pdf" not in ct and "text/html" in ct:
                    return b""
            return body
    except Exception:
        return b""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes. Returns empty string on error."""
    if not pdf_bytes or len(pdf_bytes) < 100:
        return ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        return "\n".join(parts).strip()
    except Exception:
        return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks. Preserve paragraph boundaries when possible."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        # Prefer breaking at newline or sentence end
        search = text[start:end]
        last_br = search.rfind("\n")
        if last_br > chunk_size // 2:
            end = start + last_br + 1
        else:
            for sep in (". ", ".\n", "? ", "! "):
                idx = search.rfind(sep)
                if idx > chunk_size // 2:
                    end = start + idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = end
    return chunks


def _search_content(raw: str) -> str:
    """Normalize for search: collapse whitespace, single line."""
    if not raw:
        return ""
    return " ".join(re.split(r"\s+", raw.strip()))


def build_chunk_doc(
    resource_id: str,
    palette_id: str,
    title: str,
    chunk_index: int,
    total_chunks: int,
    exact_content: str,
    record_type: str = None,
    link: str = None,
) -> Dict[str, Any]:
    """Build one chunk document in the required format."""
    chunk_id = f"{resource_id}_{chunk_index}" if total_chunks > 1 else resource_id
    metadata = {
        "id": chunk_id,
        "resource_id": resource_id,
        "paletteId": palette_id,
        "title": title,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "recordType": record_type,
        "link": link,
        "fileType": "pdf",
    }
    metadata_str = json.dumps(metadata, indent=2, ensure_ascii=False)
    search_content = _search_content(exact_content)
    # text: markdown with embedded JSON block + readable content (for RAG/vector format)
    text_body = (
        f"\n\n```json\n{metadata_str}\n```\n\n"
        f"## Resource: {title or 'PDF'}\n\n"
        f"- **Palette ID:** `{palette_id}`\n"
        f"- **Chunk:** {chunk_index + 1} / {total_chunks}\n\n"
        f"### Content\n\n{exact_content}"
    )
    return {
        "_id": chunk_id,
        "paletteId": palette_id,
        "exact_content": exact_content,
        "search_content": search_content,
        "text": text_body.strip(),
        "metadata": metadata,
    }


async def build_pdf_chunks(
    pdf_resources: List[Dict[str, Any]],
    download_base: str,
    auth_headers: Optional[Dict[str, str]] = None,
    concurrency: int = 4,
) -> List[Dict[str, Any]]:
    """
    For each PDF resource ({ _id, paletteId, fileId, title }), download PDF, extract text,
    chunk, and return list of chunk documents. Uses get_hub_headers() when auth_headers is None.
    """
    if not pdf_resources:
        return []
    headers = auth_headers if auth_headers is not None else _get_hub_headers()
    chunks_out: List[Dict[str, Any]] = []
    sem = asyncio.Semaphore(concurrency)
    total = len(pdf_resources)
    done_count: List[int] = [0]  # mutable so process_one can update

    async def process_one(session: aiohttp.ClientSession, entry: Dict[str, Any]) -> None:
        async with sem:
            resource_id = entry.get("_id") or ""
            palette_id = entry.get("paletteId") or ""
            file_id = entry.get("fileId") or ""
            pdf_url = entry.get("pdf_url") or ""
            title = (entry.get("title") or "").strip()
            if file_id:
                pdf_bytes = await download_pdf(session, file_id, download_base, headers)
            elif pdf_url:
                pdf_bytes = await download_pdf_from_url(session, pdf_url, headers)
            else:
                done_count[0] += 1
                return
            if not pdf_bytes or not _is_pdf_bytes(pdf_bytes):
                done_count[0] += 1
                return
            full_text = extract_text_from_pdf(pdf_bytes)
            if not full_text:
                done_count[0] += 1
                return
            text_chunks = chunk_text(full_text)
            for i, exact in enumerate(text_chunks):
                doc = build_chunk_doc(
                    resource_id=resource_id,
                    palette_id=palette_id,
                    title=title,
                    chunk_index=i,
                    total_chunks=len(text_chunks),
                    exact_content=exact,
                )
                chunks_out.append(doc)
            done_count[0] += 1
            if done_count[0] % 20 == 0 or done_count[0] == total:
                _log.info("PDF chunks: %d / %d resources processed.", done_count[0], total)

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[process_one(session, entry) for entry in pdf_resources])
    return chunks_out
