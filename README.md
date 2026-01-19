# Audio Translation Service

A simple web application built with FastAPI that translates audio files from any language to English text using OpenAI's Audio API.

## Features

- 🌍 Translate audio from any supported language to English
- 🎨 Modern, user-friendly web interface
- 📁 Drag and drop file upload
- ✅ Supports multiple audio formats (MP3, MP4, WAV, etc.)
- ⚡ Fast and efficient translation using OpenAI's Whisper model

## Supported Audio Formats

- MP3
- MP4
- MPEG
- MPGA
- M4A
- WAV
- WEBM

**Maximum file size:** 25 MB

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```
   
   Get your API key from: https://platform.openai.com/api-keys

3. **Run the application:**
   ```bash
   python main.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn main:app --reload
   ```

4. **Open your browser:**
   Navigate to `http://localhost:8000`

## Usage

1. Click the upload area or drag and drop an audio file
2. Click "Translate to English" button
3. Wait for the translation to complete
4. View the translated English text

## API Endpoints

- `GET /` - Web UI
- `POST /api/translate` - Translate audio file to English
- `GET /health` - Health check endpoint

## Example API Usage

```bash
curl -X POST "http://localhost:8000/api/translate" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/audio.mp3"
```

## Requirements

- Python 3.9+
- OpenAI API key
- Internet connection

## License

MIT
