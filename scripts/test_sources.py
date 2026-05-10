"""Sanity-check that each source kind can be reached from this machine.
Useful first step after install — if your network blocks one, you'll see it here.

    python scripts/test_sources.py
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain.sources import FETCHERS

PROBES = [
    ("hackernews", "top",                                 3),
    ("reddit",     "startups",                            3),
    ("rss",        "https://news.ycombinator.com/rss",    3),
    ("bluesky",    "ai agents",                           3),
]


def main():
    for kind, handle, limit in PROBES:
        print(f"\n--- {kind} :: {handle} ---")
        try:
            items = FETCHERS[kind](handle, limit=limit)
            print(f"  ok, {len(items)} items")
            for it in items[:2]:
                print(f"    · {(it.get('title') or '')[:80]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
