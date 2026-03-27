"""
config.py — single source of truth for all env vars.
All four pipeline scripts import from here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=False)

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_DATA_URI    = os.environ["MONGO_DATA_URI"]
MONGO_DEFAULT_URI = os.environ["MONGO_DEFAULT_URI"]
DATA_DB           = "hub365-data"
DEFAULT_DB        = "hub365-os"

# ── Collections ───────────────────────────────────────────────────────────────
MICROKNOWLEDGE         = os.environ["MICROKNOWLEDGE"]
MKCARDS                = os.environ["MKCARDS"]
PALETTE_MICROKNOWLEDGE = os.environ["PALETTE_MICROKNOWLEDGE"]
CREDITS                = os.environ["CREDITS"]
MICROFILES             = os.environ["MICROFILES"]
MKBOOKMARK             = os.environ["MKBOOKMARK"]
PALETTECOMMENTS        = os.environ["PALETTECOMMENTS"]
PALETTEPROJECTS        = os.environ["PALETTEPROJECTS"]
SPLASHSCREEN           = os.environ["SPLASHSCREEN"]
PROJECTS               = os.environ["PROJECTS"]
PEOPLE                 = os.environ["PEOPLE"]
PRACTICE               = os.environ["PRACTICE"]

# ── Hub ───────────────────────────────────────────────────────────────────────
HUB_CLIENT_ID         = os.getenv("HUB_CLIENT_ID", "")
HUB_CLIENT_SECRET     = os.getenv("HUB_CLIENT_SECRET", "")
HUB_AUTH_COOKIE       = os.getenv("HUB_AUTH_COOKIE", "")
HUB_FILE_DOWNLOAD_URL = os.getenv("HUB_FILE_DOWNLOAD_URL", "https://files.hub.perkinswill.com/download").rstrip("/")
HUB_CARD_BASE_URL     = os.getenv("HUB_CARD_BASE_URL", "https://hub.perkinswill.com/6318ce1dffb963c1c1d3bb1f/").rstrip("/")

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_KEY           = os.environ["OPENAI_KEY"]
EMBEDDING_MODEL      = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))

# ── OpenSearch ────────────────────────────────────────────────────────────────
OPENSEARCH_URL      = os.environ["OPENSEARCH_URL"]
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_INDEX    = os.getenv("OPENSEARCH_INDEX", "palette_index")
OPENSEARCH_VERIFY_SSL = os.getenv("OPENSEARCH_VERIFY_SSL", "true").lower() in ("1", "true", "yes")

# ── Tuning ────────────────────────────────────────────────────────────────────
CARD_CONCURRENCY = int(os.getenv("CARD_CONCURRENCY", "10"))
PDF_CONCURRENCY  = int(os.getenv("PDF_CONCURRENCY", "5"))