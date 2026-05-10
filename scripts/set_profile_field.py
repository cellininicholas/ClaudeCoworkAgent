"""Update a single field on the user profile.

Used by the dashboard's inline-edit flow: clicking Edit on a profile field
in the Cowork artifact sends a chat message asking Claude to run this script.

Usage:
    python scripts/set_profile_field.py --field interests --value "ai, sales, founder marketing"
    python scripts/set_profile_field.py --field bio --stdin   # read from stdin

Allowed fields: name, role, company, bio, interests, voice_notes
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


ALLOWED = {"name", "role", "company", "bio", "interests", "voice_notes"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", required=True, choices=sorted(ALLOWED))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--value", help="new value as a string")
    g.add_argument("--stdin", action="store_true", help="read value from stdin")
    args = ap.parse_args()

    db.init_db()
    profile = db.get_user_profile() or {}
    new_value = sys.stdin.read().strip() if args.stdin else args.value
    if args.field == "company" and not new_value:
        new_value = None  # company is the only nullable field

    payload = {
        "name":       profile.get("name", ""),
        "role":       profile.get("role", ""),
        "company":    profile.get("company"),
        "bio":        profile.get("bio", ""),
        "interests":  profile.get("interests", ""),
        "voice_notes":profile.get("voice_notes"),
    }
    payload[args.field] = new_value

    if not payload["name"] or not payload["role"] or not payload["bio"] or not payload["interests"]:
        # required fields are missing — fall back to placeholders so upsert doesn't error
        payload["name"] = payload["name"] or "(set me)"
        payload["role"] = payload["role"] or "Founder"
        payload["bio"] = payload["bio"] or "I post about what's working and what isn't."
        payload["interests"] = payload["interests"] or "ai, founder marketing"

    db.upsert_user_profile(**payload)
    db.log_audit("profile_update", f"Updated profile.{args.field}", {"field": args.field})
    print(json.dumps({"updated": args.field}))


if __name__ == "__main__":
    main()
