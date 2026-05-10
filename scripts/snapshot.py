"""Output a single JSON snapshot containing everything the dashboard renders.

Cowork artifacts can't call workspace bash (only connector MCPs are accessible
from the sandboxed artifact runtime). Instead, the /view skill runs this script
once at artifact-creation time and bakes the result into the HTML. To refresh,
the user re-runs /view.

Output schema:
{
  "generated_at": "ISO timestamp",
  "stats": {raw_items, pending_extraction, active_claims, concepts, pending_suggestions},
  "trends": [{id, name, momentum, occurrences, last_seen_at, claims: [...]}, ...],
  "suggestions": [{id, kind, headline, body, rationale, concept_ids, source_ids, callback_to, created_at, feedback}, ...],
  "sources": [{id, kind, handle, label, reliability, n_items, last_fetch_at, enabled}, ...],
  "audit": [{action, detail, created_at}, ...],
  "profile": {...} | null
}
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db, config as sb_config


def main():
    db.init_db()
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    with db.cursor() as cur:
        # stats
        cur.execute("SELECT COUNT(*) FROM raw_items"); raw_items = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM raw_items WHERE id NOT IN (SELECT raw_item_id FROM claims)")
        pending = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM claims WHERE valid_to IS NULL"); active_claims = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM concepts WHERE archived = 0"); concepts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM suggestions WHERE feedback IS NULL"); pending_sug = cur.fetchone()[0]
        out["stats"] = {
            "raw_items": raw_items, "pending_extraction": pending,
            "active_claims": active_claims, "concepts": concepts,
            "pending_suggestions": pending_sug,
        }

        # trends (with up to 3 sample claims each)
        cur.execute("""SELECT id, name, momentum, occurrences, first_seen_at, last_seen_at
                       FROM concepts WHERE archived = 0 ORDER BY momentum DESC LIMIT 50""")
        trends = [dict(r) for r in cur.fetchall()]
        for t in trends:
            cur.execute("""SELECT cl.id, cl.text, cl.stance, r.url, r.title
                           FROM claims cl JOIN claim_concepts cc ON cc.claim_id = cl.id
                           JOIN raw_items r ON r.id = cl.raw_item_id
                           WHERE cc.concept_id = ? AND cl.valid_to IS NULL
                           ORDER BY cl.created_at DESC LIMIT 3""", (t["id"],))
            t["claims"] = [dict(x) for x in cur.fetchall()]
        out["trends"] = trends

        # suggestions
        cur.execute("""SELECT id, kind, headline, body, rationale, concept_ids, source_ids,
                              callback_to, created_at, feedback
                       FROM suggestions ORDER BY created_at DESC LIMIT 30""")
        sugs = []
        for r in cur.fetchall():
            d = dict(r)
            d["concept_ids"] = json.loads(d.get("concept_ids") or "[]")
            d["source_ids"] = json.loads(d.get("source_ids") or "[]")
            sugs.append(d)
        out["suggestions"] = sugs

        # sources (with item counts)
        cur.execute("SELECT id, kind, handle, label, enabled, reliability, last_fetch_at FROM sources ORDER BY id")
        sources = [dict(r) for r in cur.fetchall()]
        for s in sources:
            cur.execute("SELECT COUNT(*) FROM raw_items WHERE source_id = ?", (s["id"],))
            s["n_items"] = cur.fetchone()[0]
            s["enabled"] = bool(s["enabled"])
        out["sources"] = sources

        # audit log (recent 200)
        cur.execute("SELECT action, detail, created_at FROM audit_log ORDER BY id DESC LIMIT 200")
        out["audit"] = [dict(r) for r in cur.fetchall()]

        # profile
        out["profile"] = db.get_user_profile()

    # healing config (read-only; surfaced for transparency)
    out["config"] = {
        "momentum_half_life_days": sb_config.MOMENTUM_HALF_LIFE_DAYS,
        "stale_concept_days": sb_config.STALE_CONCEPT_DAYS,
        "max_audit_concepts": sb_config.MAX_AUDIT_CONCEPTS,
        "ingest_limit_per_source": sb_config.INGEST_LIMIT_PER_SOURCE,
        "model": sb_config.MODEL,
        "writer_model": sb_config.WRITER_MODEL,
        "db_path": str(sb_config.DB_PATH),
    }

    json.dump(out, sys.stdout, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
