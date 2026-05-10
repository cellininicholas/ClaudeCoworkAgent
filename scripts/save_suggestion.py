"""Persist a single drafted post from the Cowork session.

Usage:
    python scripts/save_suggestion.py --json '{"headline":"...","body":"...","rationale":"...","concept_ids":[1,2],"source_ids":[3],"callback_to":null}'
    cat post.json | python scripts/save_suggestion.py --stdin
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db
from signal_brain.suggester import save_post


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json")
    g.add_argument("--stdin", action="store_true")
    args = ap.parse_args()
    raw = sys.stdin.read() if args.stdin else args.json
    p = json.loads(raw)
    db.init_db()
    sid = save_post(
        p.get("headline", ""),
        p.get("body", ""),
        p.get("rationale", ""),
        concept_ids=p.get("concept_ids") or [],
        source_ids=p.get("source_ids") or [],
        callback_to=p.get("callback_to"),
        kind=p.get("kind"),
    )
    db.log_audit("suggest", f"Suggestion #{sid} saved by Cowork session")
    print(json.dumps({"id": sid}))


if __name__ == "__main__":
    main()
