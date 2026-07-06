"""
Deep Researcher - Multi-Source Deep Research Engine
Uses Obscura headless browser for anti-detect scraping + recursive methodology.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
REPORTS_DIR = STORAGE_DIR / "reports"
CACHE_DIR = STORAGE_DIR / "cache"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OBSCURA_BIN = os.environ.get("OBSCURA_BIN", "obscura")
OBSCURA_PORT = int(os.environ.get("OBSCURA_PORT", "9222"))

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:8765")
DEFAULT_MODEL_ID = int(os.environ.get("DEFAULT_MODEL_ID", "50"))

MAX_DEPTH = int(os.environ.get("MAX_DEPTH", "3"))
MAX_SOURCES_PER_QUERY = int(os.environ.get("MAX_SOURCES_PER_QUERY", "8"))
MAX_SUB_QUERIES = int(os.environ.get("MAX_SUB_QUERIES", "7"))

PAGE_FETCH_TIMEOUT = int(os.environ.get("PAGE_FETCH_TIMEOUT", "30"))
INTER_PAGE_DELAY = float(os.environ.get("INTER_PAGE_DELAY", "0.5"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
]
