"""
Download a PDF from a public URL, extract text and images in order.
Send each image to VLM for description (openai_llms), integrate into text.
Send full markdown to LLM to refine (headings, remove repeated logos, OCR dupes, neat tables).
Output: same markdown file + images folder.
Run: python pdf_test.py
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitz
import aiohttp

from src.llm_models.openai_llms import OpenAIClient

# --- Hardcode these (public URL, no auth) ---
PDF_URL = "https://www.lifecyclebuilding.org/docs/DfDseattle.pdf"
OUT_MD = "pdf_test_output.md"
IMAGES_DIR = "pdf_test_images"


async def download_pdf(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            return await resp.read()


def get_page_items(page):
    """Text blocks and images for one page, sorted top to bottom."""
    items = []
    for block in (page.get_text("dict") or {}).get("blocks", []):
        bbox = block.get("bbox")
        if not bbox:
            continue
        text = "\n".join(
            span.get("text", "")
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        ).strip()
        if text:
            items.append((bbox[1], "text", {"text": text}))
    for img in page.get_images(full=True) or []:
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
            if rects:
                items.append((rects[0].y0, "image", {"xref": xref}))
        except Exception:
            pass
    items.sort(key=lambda x: (x[0], x[1] == "text"))
    return items


async def pdf_to_markdown(pdf_bytes: bytes, images_dir: str) -> str:
    """Build markdown with text + image refs + VLM description for each image. Returns full markdown string."""
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    lines = ["# PDF Export", ""]
    img_count = 0
    vlm = OpenAIClient()

    for pno in range(len(doc)):
        page = doc[pno]
        if pno > 0:
            lines.extend(["---", ""])
        lines.append(f"## Page {pno + 1}")
        lines.append("")

        for _, kind, payload in get_page_items(page):
            if kind == "text":
                lines.append(payload["text"])
                lines.append("")
            else:
                try:
                    im = doc.extract_image(payload["xref"])
                    ext = im.get("ext", "png").lower()
                    if ext not in ("png", "jpg", "jpeg", "gif"):
                        ext = "png"
                    img_count += 1
                    name = f"page{pno}_{img_count}.{ext}"
                    path = os.path.join(images_dir, name)
                    with open(path, "wb") as f:
                        f.write(im["image"])
                    # VLM description (integrate into text)
                    b64 = base64.b64encode(im["image"]).decode("ascii")
                    try:
                        desc = await vlm.get_description(b64)
                        lines.append(f"*[Image description]: {desc}*")
                        lines.append("")
                    except Exception:
                        pass
                    # Image ref (relative to OUT_MD; we don't know out_md here so use images_dir name)
                    lines.append(f"![Image {img_count}]({IMAGES_DIR}/{name})")
                    lines.append("")
                except Exception:
                    lines.extend(["[Image failed]", ""])

    doc.close()
    return "\n".join(lines)


async def main():
    print("Downloading PDF...")
    pdf_bytes = await download_pdf(PDF_URL)
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        print("Not a PDF.", file=sys.stderr)
        sys.exit(1)

    print("Extracting text and images, getting VLM descriptions...")
    markdown = await pdf_to_markdown(pdf_bytes, IMAGES_DIR)

    print("Refining markdown with LLM...")
    refined = await OpenAIClient().refine_markdown(markdown)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(refined)
    print(f"Wrote {OUT_MD}, images in {IMAGES_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
