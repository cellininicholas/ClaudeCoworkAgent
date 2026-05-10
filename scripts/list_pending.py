"""List raw_items that have no claims yet (pending extraction).

Used by Cowork-managed mode: the session calls this, picks items, extracts, then
calls save_extraction.py for each.

Output: JSON array on stdout. Each entry has the fields the extractor needs.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    db.init_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT r.id, r.title, r.url, r.body, s.kind || ':' || s.handle AS source
            FROM raw_items r
            JOIN sources s ON s.id = r.source_id
            WHERE r.id NOT IN (SELECT raw_item_id FROM claims)
            ORDER BY r.fetched_at DESC LIMIT ?
        """, (args.limit,))
        rows = [dict(r) for r in cur.fetchall()]
    json.dump(rows, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
