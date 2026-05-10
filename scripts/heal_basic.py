"""Run the non-LLM healing layers (decay, archive stale, feedback nudges).
Always safe. Used by both direct mode and Cowork-managed mode."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db, healing


def main():
    db.init_db()
    out = healing.run_basic_audit()
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
