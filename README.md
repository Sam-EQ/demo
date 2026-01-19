# Audio Translation Service

A modern web application built with FastAPI that translates audio files from any language to English text using OpenAI's Whisper model. Features real-time streaming translation with Server-Sent Events (SSE) for large files.

## Features

- 🌍 **Multi-language Support** - Translate audio from any supported language to English
- ⚡ **Streaming Translation** - Real-time translation updates using Server-Sent Events
- 📦 **Large File Support** - Handle files up to 250MB (automatically chunked into 22MB segments)
- 🎨 **Modern Web UI** - Clean, responsive interface with live progress updates
- 🔄 **Chunked Processing** - Large files are automatically split and processed in parallel
- 📁 **Multiple Formats** - Support for MP3, MP4, WAV, and other common audio formats
- 🛠️ **Audio Preprocessing** - Optional utilities for audio optimization (silence removal, resampling)

## Project Structure

```
demo/
├── main.py                 # FastAPI application with streaming endpoints
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in git)
├── .gitignore             # Git ignore rules
├── templates/
│   └── index.html         # Web UI with SSE client
├── audio_utils/
│   ├── __init__.py
│   └── preprocess.py      # Audio preprocessing utilities (FFmpeg)
└── README.md              # This file
```

## Supported Audio Formats

- MP3
- MP4
- MPEG
- MPGA
- M4A
- WAV
- WEBM

**Maximum file size:** 250 MB (automatically chunked)

## Setup

### Prerequisites

- Python 3.9 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- Internet connection

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd demo
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   
   Create a `.env` file in the project root:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   ```
   
   Get your API key from: https://platform.openai.com/api-keys

5. **Run the application:**
   ```bash
   python main.py
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn main:app --reload
   ```

6. **Open your browser:**
   Navigate to `http://localhost:8000`

## Usage

### Web Interface

1. Open `http://localhost:8000` in your browser
2. Click "Choose File" and select an audio file
3. Click "Translate" button
4. Watch the translation appear in real-time as chunks are processed
5. The result will display the complete translated text

### API Endpoints

#### `GET /`
Serves the web interface.

#### `POST /api/translate/stream`
Streaming translation endpoint using Server-Sent Events (SSE).

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `file` (audio file)

**Response:**
- Content-Type: `text/event-stream`
- Events:
  - `chunk` - Translation chunk with text
  - `error` - Error occurred
  - `done` - Translation complete

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/api/translate/stream" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/audio.mp3"
```

**Example using Python:**
```python
import requests

with open("audio.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/translate/stream",
        files={"file": f},
        stream=True
    )
    
    for line in response.iter_lines():
        if line:
            print(line.decode())
```

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## How It Works

1. **File Upload** - User uploads an audio file through the web interface
2. **Validation** - File type and size are validated (max 250MB)
3. **Chunking** - Large files are split into 22MB chunks
4. **Streaming Translation** - Each chunk is sent to OpenAI's Whisper API
5. **Real-time Updates** - Translation results are streamed back to the client via SSE
6. **Result Display** - Translated text appears incrementally in the web UI

## Audio Preprocessing (Optional)

The `audio_utils/preprocess.py` module provides utilities for audio preprocessing using FFmpeg:

- Silence removal
- Mono conversion
- Resampling to 16kHz

**Note:** Requires FFmpeg to be installed on your system. Currently not integrated into the main translation flow, but available for future use.

## Configuration

### Environment Variables

- `OPENAI_API_KEY` (required) - Your OpenAI API key

### Application Settings

Edit `main.py` to customize:
- `CHUNK_SIZE_MB` - Size of chunks for large files (default: 22MB)
- `ALLOWED_EXTENSIONS` - Supported file extensions
- Maximum file size limit (default: 250MB)

## Error Handling

The application handles various error scenarios:
- Invalid file types
- Files exceeding size limits
- API quota/rate limit errors
- Network connectivity issues
- Translation failures

Errors are displayed in the web UI and logged on the server.

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Logging

Logs are output to the console with INFO level. To change logging level, modify:
```python
logging.basicConfig(level=logging.INFO)  # Change to DEBUG, WARNING, etc.
```

## Requirements

- Python 3.9+
- FastAPI 0.115.0+
- OpenAI Python SDK 1.54.0+
- Uvicorn (with standard extras)
- Python-dotenv
- Jinja2

See `requirements.txt` for exact versions.

## Troubleshooting

### Common Issues

1. **"OPENAI_API_KEY is not set"**
   - Ensure `.env` file exists with your API key
   - Check that `python-dotenv` is installed

2. **"API quota exceeded"**
   - Check your OpenAI account billing and usage limits
   - Visit https://platform.openai.com/account/billing

3. **"Unsupported file type"**
   - Ensure your file has one of the supported extensions
   - Check file extension is lowercase

4. **Translation fails**
   - Check your internet connection
   - Verify your OpenAI API key is valid
   - Check server logs for detailed error messages

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
