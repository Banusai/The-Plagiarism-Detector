from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indexes"
REFERENCE_ORIGINALS_DIR = DATA_DIR / "reference_originals"
REFERENCE_METADATA_FILE = DATA_DIR / "reference_documents.json"

DEFAULT_THRESHOLD = 0.65
TOP_K = 5
FINAL_TOP_N = 3
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_UPLOAD = 5
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_TOKEN_SECRET = os.getenv("ADMIN_TOKEN_SECRET", "")

ALLOWED_EXTENSIONS = {".txt", ".pdf"}
ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "application/pdf",
    "application/octet-stream",
}
