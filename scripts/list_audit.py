"""List recent audit-log entries as JSON. Used by the dashboard artifact."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()
    db.init_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, action, detail, metadata, created_at
            FROM audit_log ORDER BY created_at DESC LIMIT ?
        """, (args.limit,))
        rows = [dict(r) for r in cur.fetchall()]
    json.dump(rows, sys.stdout, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
