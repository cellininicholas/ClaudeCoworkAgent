"""Mark one claim as superseded by another (contradiction resolution).

Usage:
    python scripts/save_supersede.py --loser 12 --winner 17 --concept "ai agents" --reason "..."
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db, healing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loser", type=int, required=True)
    ap.add_argument("--winner", type=int, required=True)
    ap.add_argument("--concept", required=True)
    ap.add_argument("--reason", default="")
    args = ap.parse_args()
    db.init_db()
    healing.supersede_claim(args.loser, args.winner, args.concept, args.reason)
    print(f"OK: claim #{args.loser} superseded by claim #{args.winner}")


if __name__ == "__main__":
    main()
