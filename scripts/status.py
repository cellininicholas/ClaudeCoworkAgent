"""Show a quick agent status — counts + top trends + recent audit. Useful for the Cowork session to inspect state."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


def main():
    db.init_db()
    out = {}
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_items"); out["raw_items"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM raw_items WHERE id NOT IN (SELECT raw_item_id FROM claims)")
        out["pending_extraction"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM claims WHERE valid_to IS NULL"); out["active_claims"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM concepts WHERE archived = 0"); out["concepts"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM suggestions WHERE feedback IS NULL"); out["pending_suggestions"] = cur.fetchone()[0]
        cur.execute("SELECT name, momentum FROM concepts WHERE archived = 0 ORDER BY momentum DESC LIMIT 8")
        out["top_trends"] = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT action, detail, created_at FROM audit_log ORDER BY id DESC LIMIT 8")
        out["recent_audit"] = [dict(r) for r in cur.fetchall()]
    json.dump(out, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
