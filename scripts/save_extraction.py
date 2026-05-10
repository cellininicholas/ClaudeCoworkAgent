"""Persist an extraction result for a single raw item.

Called by Cowork-managed mode: the session reads a pending item via
`list_pending.py`, runs the EXTRACTION_PROMPT itself, and calls this script
with the result.

Usage:
    python scripts/save_extraction.py --raw-id 42 --json '{"skip": false, "claims": [...], "concepts": [...]}'

Or pipe JSON on stdin:
    cat result.json | python scripts/save_extraction.py --raw-id 42 --stdin
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db
from signal_brain.extractor import normalise


def _upsert_concept(cur: sqlite3.Cursor, name: str) -> int:
    cur.execute("SELECT id FROM concepts WHERE name = ? COLLATE NOCASE", (name,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE concepts SET occurrences = occurrences + 1, last_seen_at = datetime('now') WHERE id = ?",
            (row[0],),
        )
        return row[0]
    cur.execute("INSERT INTO concepts (name, occurrences) VALUES (?, 1) RETURNING id", (name,))
    return cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-id", type=int, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", help="extraction result as a JSON string")
    g.add_argument("--stdin", action="store_true", help="read JSON from stdin")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.stdin else args.json
    try:
        data = normalise(json.loads(raw))
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}", file=sys.stderr); sys.exit(2)

    db.init_db()
    if data.get("skip"):
        db.log_audit("extract", f"raw_item #{args.raw_id} marked skip")
        print(json.dumps({"raw_id": args.raw_id, "skip": True}))
        return

    conn = db.connect()
    cur = conn.cursor()
    try:
        claim_ids = []
        for claim in data["claims"]:
            cur.execute("""
                INSERT INTO claims (raw_item_id, text, stance, confidence)
                VALUES (?, ?, ?, ?) RETURNING id
            """, (args.raw_id, claim["text"], claim["stance"], claim["confidence"]))
            cid = cur.fetchone()[0]
            claim_ids.append(cid)
            for concept in data["concepts"]:
                concept_id = _upsert_concept(cur, concept)
                try:
                    cur.execute("INSERT INTO claim_concepts (claim_id, concept_id) VALUES (?, ?)", (cid, concept_id))
                except sqlite3.IntegrityError:
                    pass
    finally:
        conn.close()

    db.log_audit("extract", f"raw_item #{args.raw_id} → {len(claim_ids)} claims, {len(data['concepts'])} concepts")
    print(json.dumps({"raw_id": args.raw_id, "claim_ids": claim_ids, "concepts": data["concepts"]}))


if __name__ == "__main__":
    main()
