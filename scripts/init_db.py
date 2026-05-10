"""Initialise the SQLite DB and seed default sources + (optionally) a user profile.

Run once after `pip install -r requirements.txt`:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


DEFAULT_SOURCES = [
    ("hackernews", "top",        "Hacker News (top stories)"),
    ("reddit",     "startups",   "r/startups"),
    ("reddit",     "sales",      "r/sales"),
    ("reddit",     "marketing",  "r/marketing"),
    ("rss",        "https://news.ycombinator.com/rss", "HN RSS (mirror)"),
    ("bluesky",    "AI agents",  "Bluesky search: AI agents"),
]


def main():
    db.init_db()
    print(f"Initialised DB at {db.config.DB_PATH}")
    for kind, handle, label in DEFAULT_SOURCES:
        sid = db.upsert_source(kind, handle, label)
        print(f"  source #{sid}: {kind} :: {handle}")
    if not db.get_user_profile():
        # Seed a placeholder so the agent can run end-to-end before the user fills it in.
        db.upsert_user_profile(
            name="(set me)", role="Founder",
            company=None,
            bio="Builder shipping AI-native products. I post about what's working and what isn't.",
            interests="ai agents, b2b sales, founder marketing, product, fundraising",
            voice_notes="Punchy, one idea per post, no buzzwords, no emojis, opens with a hook, ends with a question.",
        )
        print("  seeded placeholder user_profile (edit at /profile)")
    print("Done. Edit data with: python -m signal_brain.web  → http://localhost:8787/profile")


if __name__ == "__main__":
    main()
