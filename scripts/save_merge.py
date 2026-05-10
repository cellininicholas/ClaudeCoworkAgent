"""Persist a concept-merge plan from the Cowork session.

Usage:
    python scripts/save_merge.py --json '{"merges": [{"canonical": "ai agents", "aliases": ["agentic ai"]}]}'
    cat plan.json | python scripts/save_merge.py --stdin
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db, healing


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json")
    g.add_argument("--stdin", action="store_true")
    args = ap.parse_args()
    raw = sys.stdin.read() if args.stdin else args.json
    data = json.loads(raw)
    db.init_db()
    out = healing.apply_merges(data.get("merges") or [])
    print(json.dumps(out))


if __name__ == "__main__":
    main()
