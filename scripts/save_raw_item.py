"""Persist one raw item fetched by the Cowork session via WebFetch.

The Cowork session calls this once per new item it parsed out of a source feed.
Content-hash dedup means re-running across cycles is safe.

Usage:
    python scripts/save_raw_item.py --source-id 1 --json '{"external_id":"...","title":"...","url":"...","body":"...","posted_at":"...","score":0}'

Or pipe via stdin:
    cat item.json | python scripts/save_raw_item.py --source-id 1 --stdin
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def _hash(item: dict) -> str:
    payload = (item.get("title", "") + "|" + item.get("url", "") + "|" + (item.get("body") or "")[:500])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-id", type=int, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="raw_item as a JSON string")
    g.add_argument("--stdin", action="store_true", help="read JSON from stdin")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.stdin else args.json
    try:
        item = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}", file=sys.stderr); sys.exit(2)

    db.init_db()
    content_hash = _hash(item)

    conn = db.connect()
    cur = conn.cursor()
    try:
        # exact-hash global dedup
        cur.execute("SELECT id FROM raw_items WHERE content_hash = ?", (content_hash,))
        if cur.fetchone():
            print(json.dumps({"skipped": True, "reason": "duplicate"}))
            return
        try:
            cur.execute("""
                INSERT INTO raw_items (source_id, external_id, title, url, body, score, posted_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
            """, (
                args.source_id,
                str(item.get("external_id") or content_hash[:16]),
                (item.get("title") or "")[:500],
                item.get("url") or "",
                item.get("body") or "",
                int(item.get("score") or 0),
                item.get("posted_at") or "",
                content_hash,
            ))
            row = cur.fetchone()
        except sqlite3.IntegrityError:
            print(json.dumps({"skipped": True, "reason": "external_id collision"}))
            return
    finally:
        conn.close()

    print(json.dumps({"id": row[0]}))


if __name__ == "__main__":
    main()
