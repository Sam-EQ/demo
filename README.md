# Audio Transcription & Translation Backend

A production-ready FastAPI backend service for audio file ingestion, preprocessing, speech-to-text transcription, and translation using OpenAI APIs.

## Features

- **Audio Ingestion**: Accept audio files via REST API (multipart/form-data)
- **Audio Preprocessing**: Normalize, trim silence, and chunk audio using FFmpeg
- **Speech-to-Text**: Transcribe audio using OpenAI Whisper API
- **Language Detection**: Automatic language detection from audio
- **Translation**: Translate transcripts using OpenAI GPT-4o-mini
- **Supported Languages**: English (en), Danish (da), French (fr), Portuguese (pt), Mandarin Chinese - Simplified (zh-Hans)

## Prerequisites

- **Python 3.11** or higher (for local development)
- **FFmpeg** installed and available in your PATH (for local development)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)
- **OpenAI API Key** (set via environment variable)
- **Docker and Docker Compose** (for containerized deployment)

## Quick Start with Docker

1. Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   # Edit .env and set your OPENAI_API_KEY
   ```

2. Start the service:
   ```bash
   docker-compose up --build
   ```

3. The API will be available at `http://localhost:8000`

4. View API documentation at `http://localhost:8000/docs`

To stop the service:
```bash
docker-compose down
```

## Installation (Local Development)

1. Clone or navigate to the project directory:
   ```bash
   cd /path/to/demo
   ```

2. Create a virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (defaults shown)
# TEMP_DIR=/tmp/audio_processing
# MAX_AUDIO_DURATION_SECONDS=300
# MAX_FILE_SIZE_BYTES=10485760
# CHUNK_MAX_LENGTH_SECONDS=60
# TARGET_LANGUAGE=en
# LOG_LEVEL=INFO
# TRANSCRIPTION_MODEL=whisper-1
# TRANSLATION_MODEL=gpt-4o-mini
```

For local development without Docker, you can also export environment variables:

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

## Running the Service

Start the FastAPI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The service will be available at:
- API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## API Usage

### Endpoint

**POST** `/api/transcribe-and-translate`

### Request

Upload an audio file using multipart/form-data:

```bash
curl -X POST "http://localhost:8000/api/transcribe-and-translate?target_language=fr" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/audio.mp3"
```

**Query Parameters:**
- `target_language` (optional): Target language code for translation. Overrides `TARGET_LANGUAGE` environment variable. Supported: `en`, `da`, `fr`, `pt`, `zh-Hans`

**Supported File Formats:**
- `.wav`
- `.mp3`
- `.m4a`

### Response

```json
{
  "original_transcript": "Hello world. This is a test transcript.",
  "detected_language": "en",
  "translated_transcript": "Bonjour le monde. Ceci est une transcription de test.",
  "metadata": {
    "audio_duration_seconds": 124.5,
    "chunk_count": 3,
    "transcription_model": "whisper-1",
    "translation_model": "gpt-4o-mini",
    "processing_time_ms": 2350
  }
}
```

### Error Responses

- **400 Bad Request**: Invalid request (unsupported language, empty file, etc.)
- **413 Payload Too Large**: File size exceeds `MAX_FILE_SIZE_BYTES`
- **415 Unsupported Media Type**: Unsupported file format
- **500 Internal Server Error**: Server error during processing

## Project Structure

```
/app
  /api
    routes.py              # FastAPI route handlers
  /services
    audio_preprocessor.py  # FFmpeg-based audio processing
    transcription_service.py  # OpenAI Whisper transcription
    translation_service.py   # OpenAI chat model translation
  /core
    config.py              # Configuration management
    logging.py             # Structured logging setup
  /models
    schemas.py             # Pydantic response models
main.py                    # FastAPI application entry point
requirements.txt           # Python dependencies
README.md                  # This file
```

## Architecture

The service follows a layered architecture:

1. **API Layer** (`/app/api`): Handles HTTP requests, validation, and responses
2. **Service Layer** (`/app/services`): Business logic for audio processing, transcription, and translation
3. **Core Layer** (`/app/core`): Configuration and logging utilities
4. **Models Layer** (`/app/models`): Pydantic schemas for data validation

### Processing Flow

1. File upload validation (format, size)
2. Audio preprocessing (normalize to mono 16kHz, trim silence, chunk)
3. Transcription of each chunk using OpenAI Whisper
4. Language detection and normalization
5. Translation using OpenAI GPT-4o-mini
6. Response assembly with metadata
7. Cleanup of temporary files

## Features & Best Practices

- **Type Safety**: Full type hints throughout the codebase
- **Error Handling**: Comprehensive error handling with meaningful HTTP status codes
- **Retry Logic**: Exponential backoff for OpenAI API calls (3 attempts)
- **File Cleanup**: Automatic cleanup of temporary files after processing
- **Logging**: Structured logging with configurable levels
- **Security**: No shell execution in subprocess calls, environment-based configuration
- **Modularity**: Clear separation of concerns, testable components

## Development

### Code Quality

- All public functions and classes have docstrings
- Type hints are required for all function parameters and return values
- Follows PEP 8 style guidelines

### Testing Considerations

- File size and format validation
- Language detection edge cases
- Chunking logic for various audio durations
- Error handling for OpenAI API failures
- Cleanup verification

## License

This project is provided as-is for enterprise production usage.

## Support

For issues or questions, please refer to the OpenAI API documentation:
- [OpenAI Audio API](https://platform.openai.com/docs/guides/speech-to-text)
- [OpenAI Chat API](https://platform.openai.com/docs/guides/text-generation)
