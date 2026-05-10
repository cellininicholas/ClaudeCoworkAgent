"""Self-healing layer.

Layered mechanisms — split into "non-LLM" (always run) and "LLM" (skipped in Cowork mode):

Non-LLM (always available):
1. Recompute concept momentum (decaying over time, weighted by source reliability).
2. Archive stale concepts.
3. Reliability nudges from user feedback on suggestions.

LLM-required (skipped under provider='cowork'; the Cowork session does these itself):
4. Concept clustering / alias merging.
5. Contradiction detection between recent claims about the same concept.

Every action writes to audit_log.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone

from . import db, config, llm

# Prompts re-used by Cowork-mode (so the slash command can show them to the session)
MERGE_PROMPT = """You are an ontology janitor. Given a list of concepts (short noun phrases),
identify groups that mean the same thing and should be merged into one canonical name.

Examples of pairs to merge:
- "ai agents" + "autonomous agents" → "ai agents"
- "llm fine-tuning" + "fine-tuning llms" → "llm fine-tuning"
- "b2b sales" + "business-to-business sales" → "b2b sales"

Examples that are DIFFERENT and must NOT be merged:
- "ai agents" vs "ai safety"
- "fundraising" vs "venture capital"

Return ONLY JSON of the form:
{"merges": [{"canonical": "ai agents", "aliases": ["autonomous agents", "agentic ai"]}]}
If nothing should be merged, return {"merges": []}."""


CONTRA_PROMPT = """You receive pairs of claims attached to the same concept.
For each pair, decide if they CONTRADICT (one implies the other is false).
Only flag clear contradictions, not differences in emphasis.

Return JSON: {"contradictions": [{"a": <id>, "b": <id>, "reason": "..."}]}"""


# --- 1. Momentum recomputation ---------------------------------------------------

def recompute_momentum() -> dict:
    """Score = sum over claims of (source_reliability * exp(-age_days / half_life))."""
    half_life = config.MOMENTUM_HALF_LIFE_DAYS
    now = datetime.now(timezone.utc)
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT cc.concept_id AS cid, c.created_at AS ts, s.reliability AS rel
        FROM claim_concepts cc
        JOIN claims c ON c.id = cc.claim_id
        JOIN raw_items r ON r.id = c.raw_item_id
        JOIN sources s ON s.id = r.source_id
        WHERE c.valid_to IS NULL
    """)
    bucket: dict[int, float] = {}
    for cid, ts, rel in cur.fetchall():
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - t).total_seconds() / 86400.0)
        weight = (rel or 0.5) * math.exp(-age_days / half_life)
        bucket[cid] = bucket.get(cid, 0.0) + weight
    cur.execute("UPDATE concepts SET momentum = 0")
    for cid, score in bucket.items():
        cur.execute("UPDATE concepts SET momentum = ? WHERE id = ?", (round(score, 4), cid))
    conn.close()
    db.log_audit("decay", f"Recomputed momentum for {len(bucket)} concepts", {"updated": len(bucket)})
    return {"updated": len(bucket)}


# --- 2. Archive stale -----------------------------------------------------------

def archive_stale() -> dict:
    cutoff_days = config.STALE_CONCEPT_DAYS
    with db.cursor() as cur:
        cur.execute("""
            UPDATE concepts SET archived = 1
            WHERE archived = 0
              AND momentum < 0.05
              AND julianday('now') - julianday(last_seen_at) > ?
            RETURNING id, name
        """, (cutoff_days,))
        archived = cur.fetchall()
    if archived:
        db.log_audit(
            "archive_concept",
            f"Archived {len(archived)} stale concepts: " + ", ".join(r[1] for r in archived[:5]) + ("..." if len(archived) > 5 else ""),
            {"ids": [r[0] for r in archived]},
        )
    return {"archived": len(archived)}


# --- 3. LLM-based concept merge -------------------------------------------------

def merge_duplicate_concepts() -> dict:
    """Direct-API path. In Cowork mode this raises NotConfigured."""
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name FROM concepts WHERE archived = 0
            ORDER BY momentum DESC LIMIT ?
        """, (config.MAX_AUDIT_CONCEPTS,))
        rows = cur.fetchall()
    if len(rows) < 2:
        return {"merges": 0, "skipped": True}
    names = [r[1] for r in rows]
    try:
        raw = llm.complete(MERGE_PROMPT, "Concepts:\n" + "\n".join(f"- {n}" for n in names),
                           max_tokens=600)
    except llm.NotConfigured:
        return {"merges": 0, "skipped": "cowork"}
    except Exception as e:
        db.log_audit("merge_error", f"merge failed: {e}")
        return {"merges": 0, "error": str(e)}

    data = llm.parse_json(raw)
    return apply_merges(data.get("merges") or [])


def apply_merges(merges: list[dict]) -> dict:
    """Persist a merge plan (used by both direct mode and Cowork's save_heal_action.py).

    Each merge: {"canonical": "...", "aliases": [...]}
    """
    applied = 0
    if not merges:
        return {"merges": 0}
    conn = db.connect()
    cur = conn.cursor()
    try:
        # build name→id map
        cur.execute("SELECT id, name FROM concepts WHERE archived = 0")
        name_to_id = {r[1].lower(): r[0] for r in cur.fetchall()}
        for group in merges:
            canonical = (group.get("canonical") or "").strip().lower()
            aliases = [a.strip().lower() for a in (group.get("aliases") or []) if a.strip()]
            canon_id = name_to_id.get(canonical)
            if not canonical or not canon_id or not aliases:
                continue
            for alias in aliases:
                if alias == canonical:
                    continue
                alias_id = name_to_id.get(alias)
                if alias_id is None or alias_id == canon_id:
                    continue
                cur.execute(
                    "UPDATE OR IGNORE claim_concepts SET concept_id = ? WHERE concept_id = ?",
                    (canon_id, alias_id),
                )
                cur.execute("DELETE FROM claim_concepts WHERE concept_id = ?", (alias_id,))
                cur.execute("DELETE FROM concepts WHERE id = ?", (alias_id,))
                applied += 1
        if applied:
            db.log_audit("merge_concepts", f"Merged {applied} alias concepts", {"merges": merges})
    finally:
        conn.close()
    return {"merges": applied}


# --- 4. Contradiction scan ------------------------------------------------------

def detect_contradictions() -> dict:
    """Direct-API path. Skipped in Cowork mode."""
    if llm.PROVIDER == "cowork":
        return {"contradictions": 0, "skipped": "cowork"}
    found = 0
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name FROM concepts
            WHERE archived = 0 AND momentum > 0.1
            ORDER BY momentum DESC LIMIT 10
        """)
        concepts = cur.fetchall()
        for cid, cname in concepts:
            cur.execute("""
                SELECT c.id, c.text, c.stance, c.confidence, s.reliability
                FROM claims c
                JOIN claim_concepts cc ON cc.claim_id = c.id
                JOIN raw_items r ON r.id = c.raw_item_id
                JOIN sources s ON s.id = r.source_id
                WHERE cc.concept_id = ? AND c.valid_to IS NULL
                ORDER BY c.created_at DESC LIMIT 12
            """, (cid,))
            claims = cur.fetchall()
            if len(claims) < 2:
                continue
            payload = [{"id": r[0], "text": r[1], "stance": r[2]} for r in claims]
            try:
                raw = llm.complete(CONTRA_PROMPT,
                                   f"Concept: {cname}\nClaims:\n" + json.dumps(payload, indent=2),
                                   max_tokens=400)
            except Exception:
                continue
            data = llm.parse_json(raw)
            for con in data.get("contradictions", [])[:3]:
                a_id = con.get("a"); b_id = con.get("b")
                if not isinstance(a_id, int) or not isinstance(b_id, int):
                    continue
                claim_map = {r[0]: r for r in claims}
                if a_id not in claim_map or b_id not in claim_map:
                    continue
                a, b = claim_map[a_id], claim_map[b_id]
                rel_a = a[4] or 0.5; rel_b = b[4] or 0.5
                winner, loser = (a, b) if rel_a >= rel_b else (b, a)
                supersede_claim(loser[0], winner[0], cname, con.get("reason", ""))
                found += 1
    return {"contradictions": found}


def supersede_claim(loser_id: int, winner_id: int, concept_name: str, reason: str = "") -> None:
    """Mark a claim as superseded by another. Used by both direct mode and Cowork mode."""
    with db.cursor() as cur:
        cur.execute("""
            UPDATE claims SET valid_to = datetime('now'), superseded_by = ?
            WHERE id = ? AND valid_to IS NULL
        """, (winner_id, loser_id))
    db.log_audit(
        "flag_contradiction",
        f"In '{concept_name}': claim #{loser_id} superseded by claim #{winner_id}",
        {"reason": reason, "winner": winner_id, "loser": loser_id},
    )


# --- 5. Reliability updates from feedback --------------------------------------

def apply_feedback() -> dict:
    delta_pos, delta_neg = 0.02, 0.03
    touched = 0
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, source_ids, feedback FROM suggestions
            WHERE feedback IS NOT NULL AND id NOT IN (
                SELECT json_extract(metadata, '$.suggestion_id') FROM audit_log
                WHERE action = 'reliability_update'
            )
        """)
        rows = cur.fetchall()
        for sug_id, source_ids_json, feedback in rows:
            try:
                ids = json.loads(source_ids_json)
            except Exception:
                ids = []
            if not ids:
                continue
            d = delta_pos if feedback == "accepted" else -delta_neg
            for sid in ids:
                cur.execute("""
                    UPDATE sources SET reliability = MAX(0.1, MIN(0.95, reliability + ?))
                    WHERE id = ?
                """, (d, sid))
            db.log_audit(
                "reliability_update",
                f"Suggestion #{sug_id} {feedback}: nudged {len(ids)} sources by {d:+.2f}",
                {"suggestion_id": sug_id, "delta": d, "sources": ids},
            )
            touched += 1
    return {"feedback_applied": touched}


# --- Orchestrators --------------------------------------------------------------

def run_basic_audit() -> dict:
    """Non-LLM healing only. Always safe to call, no API key needed."""
    return {
        "momentum": recompute_momentum(),
        "stale": archive_stale(),
        "feedback": apply_feedback(),
    }


def run_audit() -> dict:
    """Full audit including LLM steps. Skips merge/contradiction in Cowork mode."""
    out = run_basic_audit()
    out["merge"] = merge_duplicate_concepts()
    out["contradictions"] = detect_contradictions()
    return out
