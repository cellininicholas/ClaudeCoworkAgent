"""List recent suggestions as JSON. Used by the dashboard artifact."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--pending-only", action="store_true",
                   help="only return suggestions awaiting accept/reject feedback")
    args = ap.parse_args()
    db.init_db()
    where = "WHERE feedback IS NULL" if args.pending_only else ""
    with db.cursor() as cur:
        cur.execute(f"""
            SELECT id, kind, headline, body, rationale, concept_ids, source_ids,
                   callback_to, created_at, feedback
            FROM suggestions {where}
            ORDER BY created_at DESC LIMIT ?
        """, (args.limit,))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["concept_ids"] = json.loads(d.get("concept_ids") or "[]")
            d["source_ids"] = json.loads(d.get("source_ids") or "[]")
            rows.append(d)
    json.dump(rows, sys.stdout, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
