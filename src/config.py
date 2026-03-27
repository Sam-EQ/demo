import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env first (project root) so MONGO_* are available
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_dotenv()

# Hub file download auth: use raw token (same as SESSION_ID in talent_toolkit) or "authentication=<token>"
HUB_AUTH_COOKIE = os.getenv("HUB_AUTH_COOKIE", None)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

MONGO_DATA_URI = os.getenv("MONGO_DATA_URI")
MONGO_DEFAULT_URI = os.getenv("MONGO_DEFAULT_URI")

DATA_DB_NAME = "hub365-data"
DEFAULT_DB_NAME = "hub365-os"

USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")
OPENAI_API_KEY = os.getenv("OPENAI_KEY", None)
PEOPLE = os.getenv("PEOPLE", None)
PRACTICE = os.getenv("PRACTICE", None)

OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", None)
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", None)
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", None)
INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "microKnowledge_index")
OPENSEARCH_VERIFY_SSL = os.getenv("OPENSEARCH_VERIFY_SSL", "true").lower() in ("1", "true", "yes")

# Sync mode: "full" = whole Mongo data; "delta" = only docs updated after last OpenSearch max(metadata.updated_at)
MK_SYNC_MODE = (os.getenv("MK_SYNC_MODE", "full") or "full").strip().lower()

PROJECTS = os.getenv("PROJECTS", None)
COMPANY = os.getenv("COMPANY", None)
MICROKNOWLEDGE = os.getenv("MICROKNOWLEDGE", None)
MKCARDS = os.getenv("MKCARDS", None)
PALETTE_MICROKNOWLEDGE = os.getenv("PALETTE_MICROKNOWLEDGE", None)
CREDITS = os.getenv("CREDITS", None)
MICROFILES = os.getenv("MICROFILES", None)
MKBOOKMARK = os.getenv("MKBOOKMARK", None)
PALETTECOMMENTS = os.getenv("PALETTECOMMENTS", None)
PALETTEPROJECTS = os.getenv("PALETTEPROJECTS", None)
SPLASHSCREEN = os.getenv("SPLASHSCREEN", None)
# Base URL for card links (e.g. https://hub.perkinswill.com/6318ce1dffb963c1c1d3bb1f/)
HUB_CARD_BASE_URL = os.getenv("HUB_CARD_BASE_URL", "https://hub.perkinswill.com/6318ce1dffb963c1c1d3bb1f/").rstrip("/")
# Base URL for file/image IDs in content (img src may be just an ID; we resolve to full URL)
HUB_FILE_BASE_URL = os.getenv("HUB_FILE_BASE_URL", "https://hub.perkinswill.com/files/").rstrip("/")
# Direct download URL for Hub files (e.g. for classifying file type): https://files.hub.perkinswill.com/download/{fileId}
HUB_FILE_DOWNLOAD_URL = os.getenv("HUB_FILE_DOWNLOAD_URL", "https://files.hub.perkinswill.com/download").rstrip("/")

HUB_CLIENT_ID = os.getenv("HUB_CLIENT_ID", None)
HUB_CLIENT_SECRET = os.getenv("HUB_CLIENT_SECRET", None)

# PDF parser API: accepts only PDF. POST /extract with multipart form (one file field).
PDF_PARSER_API_URL = os.getenv("PDF_PARSER_API_URL", "http://localhost:8000").rstrip("/")
# Form field name for the PDF file (some APIs expect "pdf" instead of "file")
PDF_PARSER_FILE_FIELD = os.getenv("PDF_PARSER_FILE_FIELD", "file").strip() or "file"