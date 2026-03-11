import os
from dotenv import load_dotenv

load_dotenv()

def get_env(name, default=None, required=False):
    value = os.getenv(name, default)

    if required and value is None:
        raise ValueError(f"Environment variable '{name}' is required but not set.")

    return value

MONGO_DEFAULT_URL = get_env("MONGO_DEFAULT_URL", required=True)
MONGO_DATA_URL = get_env("MONGO_DATA_URL", required=True)
OPENAI_API_KEY = get_env("OPENAI_API_KEY", required=True)
OPENSEARCH_USERNAME = get_env("OPENSEARCH_USERNAME", required=True)
OPENSEARCH_PASSWORD = get_env("OPENSEARCH_PASSWORD", required=True)
INDEX_NAME = get_env("INDEX_NAME", default="marketing_toolkit")
OPENSEARCH_URL = get_env("OPENSEARCH_URL", required=True)
SESSION_ID = get_env("SESSION_ID", required=True)