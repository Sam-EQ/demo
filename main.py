import os
import tempfile
import traceback
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/translate")
async def translate_audio(file: UploadFile = File(...)):
    allowed_extensions = {
        ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"
    }

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)

    if size_mb > 25:
        raise HTTPException(status_code=400, detail="File exceeds 25 MB limit")

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(data)
            temp_path = tmp.name

        logger.info("Translating %s (%.2f MB)", file.filename, size_mb)

        with open(temp_path, "rb") as audio:
            result = client.audio.translations.create(
                model="whisper-1",
                file=audio
            )

        return JSONResponse({
            "success": True,
            "text": result.text,
            "filename": file.filename
        })

    except Exception as e:
        logger.error("Translation failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Translation failed")

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
