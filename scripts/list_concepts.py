"""List active concepts. Used by Cowork-managed mode for merge + contradiction passes.

Output: JSON array sorted by momentum descending.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--with-claims", action="store_true",
                   help="include up to 6 recent claims per concept (for contradiction analysis)")
    args = ap.parse_args()
    db.init_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name, momentum, occurrences FROM concepts
            WHERE archived = 0 ORDER BY momentum DESC LIMIT ?
        """, (args.limit,))
        rows = [dict(r) for r in cur.fetchall()]
        if args.with_claims:
            for c in rows:
                cur.execute("""
                    SELECT cl.id, cl.text, cl.stance, s.id AS source_id, s.reliability
                    FROM claims cl
                    JOIN claim_concepts cc ON cc.claim_id = cl.id
                    JOIN raw_items r ON r.id = cl.raw_item_id
                    JOIN sources s ON s.id = r.source_id
                    WHERE cc.concept_id = ? AND cl.valid_to IS NULL
                    ORDER BY cl.created_at DESC LIMIT 6
                """, (c["id"],))
                c["claims"] = [dict(r) for r in cur.fetchall()]
    json.dump(rows, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
