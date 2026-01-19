import os
import json
import logging
import asyncio
import tempfile
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from dotenv import load_dotenv

from audio_utils.preprocess import process_and_segment

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Media Scribe")
templates = Jinja2Templates(directory="templates")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
AUDIO_EXTS = {".mp3", ".mpeg", ".mpga", ".m4a", ".wav"}
ALLOWED_EXTENSIONS = VIDEO_EXTS.union(AUDIO_EXTS)

def format_srt_time(seconds: float) -> str:
    """Converts float seconds to SRT timestamp format HH:MM:SS,mmm"""
    td_hours = int(seconds // 3600)
    td_mins = int((seconds % 3600) // 60)
    td_secs = int(seconds % 60)
    td_msecs = int((seconds % 1) * 1000)
    return f"{td_hours:02d}:{td_mins:02d}:{td_secs:02d},{td_msecs:03d}"

async def generate_minutes(transcript_text: str):
    prompt = f"Analyze this transcript and provide a Meeting Minutes report in Markdown.\n\nTranscript:\n{transcript_text}"
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a professional secretary."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

async def process_media_stream(file_bytes: bytes, ext: str, should_summarize: bool):
    full_audio = None
    segments = []
    full_transcript = []
    srt_content = ""
    subtitle_index = 1
    
    # Each segment is 60 seconds (set in preprocess.py)
    CHUNK_DURATION = 60.0

    try:
        yield f"event: status\ndata: {json.dumps({'msg': 'Initializing (Mono 16kHz)...'})}\n\n"
        
        full_audio, segments = await asyncio.to_thread(process_and_segment, file_bytes, ext, segment_minutes=1.0)
        
        for i, path in enumerate(segments):
            time_offset = i * CHUNK_DURATION
            yield f"event: status\ndata: {json.dumps({'msg': f'Transcribing minute {i+1}/{len(segments)}...'})}\n\n"
            
            with open(path, "rb") as f:
                result = await asyncio.to_thread(
                    client.audio.transcriptions.create, 
                    model="whisper-1", 
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            # FIXED: Accessing segments as Objects instead of Dictionaries
            for seg in result.segments:
                start_str = format_srt_time(seg.start + time_offset)
                end_str = format_srt_time(seg.end + time_offset)
                text = seg.text.strip()
                
                srt_block = f"{subtitle_index}\n{start_str} --> {end_str}\n{text}\n\n"
                srt_content += srt_block
                subtitle_index += 1

            full_transcript.append(result.text.strip())
            padding = ":" + (" " * 1024) + "\n"
            yield f"{padding}event: chunk\ndata: {json.dumps({'text': result.text + ' '})}\n\n"

        yield f"event: srt\ndata: {json.dumps({'content': srt_content})}\n\n"

        if should_summarize:
            yield f"event: status\ndata: {json.dumps({'msg': 'Generating Meeting Minutes...'})}\n\n"
            report = await generate_minutes(" ".join(full_transcript))
            yield f"event: minutes\ndata: {json.dumps({'report': report})}\n\n"

        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    except Exception as e:
        logger.error(traceback.format_exc())
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    finally:
        if full_audio and os.path.exists(full_audio): os.remove(full_audio)
        for s in segments:
            if os.path.exists(s): os.remove(s)

@app.post("/api/translate/stream")
async def translate_endpoint(file: UploadFile = File(...), generate_minutes: bool = Query(True)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported format")
    content = await file.read()
    return StreamingResponse(process_media_stream(content, ext, generate_minutes), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)