"""Pure-data ingest: pull from sources, dedupe, insert raw_items. NO LLM calls.

Always safe to call. Cowork-managed mode runs this first, then the session
extracts pending items itself.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import ingest, db


def main():
    db.init_db()
    results = []
    with db.cursor() as cur:
        cur.execute("SELECT id, kind, handle FROM sources WHERE enabled = 1")
        sources = [dict(r) for r in cur.fetchall()]
    for s in sources:
        try:
            r = ingest.ingest_source(s["id"], s["kind"], s["handle"], 25, run_extraction=False)
            r["source"] = f"{s['kind']}:{s['handle']}"
            results.append(r)
            print(f"  {r['source']}: fetched {r['fetched']}, inserted {r['inserted']}, skipped {r['skipped']}")
        except Exception as e:
            print(f"  {s['kind']}:{s['handle']}: ERROR {e}")
            db.log_audit("ingest_error", f"{s['kind']}:{s['handle']} failed", {"error": str(e)})
    print(f"Done. Pending items will be listed by `python scripts/list_pending.py`.")


if __name__ == "__main__":
    main()
