"""Print the user profile + top concepts + callback concept as JSON,
plus the SUGGESTION_PROMPT, for the Cowork session to use when drafting posts.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db
from signal_brain.suggester import gather_context, SUGGESTION_PROMPT


def main():
    db.init_db()
    ctx = gather_context()
    out = {
        "system_prompt": SUGGESTION_PROMPT,
        "context": ctx,
    }
    json.dump(out, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
