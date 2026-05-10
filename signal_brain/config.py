"""Centralised config. Reads from .env if present, falls back to env vars, then defaults."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


REPO_ROOT = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("SIGNAL_BRAIN_MODEL", "claude-haiku-4-5-20251001")
WRITER_MODEL = os.environ.get("SIGNAL_BRAIN_WRITER_MODEL", "claude-sonnet-4-6")

DB_PATH = Path(os.environ.get("SIGNAL_BRAIN_DB", str(REPO_ROOT / "data" / "signal.db")))
SCHEMA_PATH = REPO_ROOT / "schema.sql"

PORT = int(os.environ.get("SIGNAL_BRAIN_PORT", "8765"))

# Self-healing tunables
MOMENTUM_HALF_LIFE_DAYS = 7      # how fast trend momentum decays
STALE_CONCEPT_DAYS = 30          # archive concepts not seen for this long
MAX_AUDIT_CONCEPTS = 40          # how many concepts the audit pass examines per run
INGEST_LIMIT_PER_SOURCE = 25     # max items pulled per source per ingest
