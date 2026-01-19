import os
import tempfile
import logging
import asyncio
import traceback
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv




load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audio Translation Service")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=api_key)

templates = Jinja2Templates(directory="templates")



ALLOWED_EXTENSIONS = {
    ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"
}

CHUNK_SIZE_MB = 22
CHUNK_SIZE_BYTES = CHUNK_SIZE_MB * 1024 * 1024



def chunk_bytes(data: bytes, size: int):
    for i in range(0, len(data), size):
        yield data[i:i + size]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


async def translate_audio_stream(data: bytes, ext: str):
    chunks = list(chunk_bytes(data, CHUNK_SIZE_BYTES))
    total = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(chunk)
                temp_path = tmp.name

            logger.info("Translating chunk %s/%s", index, total)

            with open(temp_path, "rb") as audio:
                result = await asyncio.to_thread(
                    client.audio.translations.create,
                    model="whisper-1",
                    file=audio
                )

            payload = {
                "chunk": index,
                "total": total,
                "text": result.text.strip()
            }

            yield (
                "event: chunk\n"
                f"data: {json.dumps(payload)}\n\n"
            )

        except Exception as e:
            logger.error("Chunk failed: %s\n%s", e, traceback.format_exc())
            yield (
                "event: error\n"
                f"data: {json.dumps({'error': str(e)})}\n\n"
            )
            return

        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    yield (
        "event: done\n"
        f"data: {json.dumps({'status': 'done'})}\n\n"
    )


@app.post("/api/translate/stream")
async def translate_audio_streaming(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)

    if size_mb > 250:
        raise HTTPException(status_code=400, detail="File too large")

    return StreamingResponse(
        translate_audio_stream(data, ext),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
