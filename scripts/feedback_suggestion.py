"""Apply accept/reject feedback to a suggestion. Used by the dashboard artifact.

This is the only write the dashboard performs. Source-reliability nudges
happen on the next basic-heal pass that reads this feedback (see
signal_brain.healing.apply_feedback).

Usage:
    python scripts/feedback_suggestion.py --id 7 --action accepted
    python scripts/feedback_suggestion.py --id 7 --action rejected
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--action", choices=("accepted", "rejected"), required=True)
    args = ap.parse_args()
    db.init_db()
    with db.cursor() as cur:
        cur.execute("UPDATE suggestions SET feedback = ? WHERE id = ?", (args.action, args.id))
        cur.execute("SELECT changes()")
        n = cur.fetchone()[0]
    if n:
        db.log_audit("suggestion_feedback", f"Suggestion #{args.id} {args.action}",
                    {"suggestion_id": args.id})
        print(json.dumps({"id": args.id, "action": args.action}))
    else:
        print(json.dumps({"error": f"no suggestion #{args.id}"}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
