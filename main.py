from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import os
from openai import OpenAI
from dotenv import load_dotenv
import tempfile
import shutil

# Load environment variables
load_dotenv()

app = FastAPI(title="Audio Translation Service")

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=api_key)

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main web UI"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/translate")
async def translate_audio(file: UploadFile = File(...)):
    """
    Translate audio file to English text using OpenAI's translations API
    """
    # Validate file type
    allowed_extensions = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (25 MB limit)
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    if file_size_mb > 25:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 25 MB limit. Please use a smaller file or compress the audio."
        )
    
    # Save uploaded file to temporary location
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Translate audio to English
        with open(temp_file_path, "rb") as audio_file:
            translation = client.audio.translations.create(
                model="whisper-1",
                file=audio_file
            )
        
        return JSONResponse({
            "success": True,
            "text": translation.text,
            "original_filename": file.filename
        })
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
