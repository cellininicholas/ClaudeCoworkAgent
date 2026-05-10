"""Full agent cycle: ingest -> heal -> suggest. This is what Cowork's scheduled
task should call. Idempotent and safe to run on a cron / interval.

Usage:
    python scripts/run_all.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import ingest, healing, suggester, db


def main():
    db.init_db()
    print("[1/3] Ingesting...")
    ing = ingest.ingest_all()
    for r in ing:
        print("  ", r)

    print("[2/3] Self-healing audit pass...")
    audit = healing.run_audit()
    print("  ", json.dumps(audit, default=str))

    print("[3/3] Generating suggestions...")
    sug = suggester.generate_suggestions()
    if "error" in sug:
        print("  error:", sug["error"])
    else:
        print(f"  digest: {sug.get('digest','')[:140]}...")
        print(f"  posts: {len(sug.get('posts', []))}")

    print("Done.")


if __name__ == "__main__":
    main()
