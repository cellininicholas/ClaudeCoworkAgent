"""Generate the daily/weekly digest + 3 post drafts (one is a 'callback')."""
from __future__ import annotations
import json
import re

from . import db, config, llm


SUGGESTION_PROMPT = """You are a content strategist for a busy founder/sales leader.
You will be given:
- Their bio + voice notes.
- The top recent CONCEPTS in their knowledge base, each with sample claims and source URLs.
- Optionally an OLDER concept that is re-emerging — use it for the 'callback' post.

Produce 3 post drafts, each tailored to the user's voice and tangentially relevant to their work.
- Post 1: ride the strongest current trend.
- Post 2: a contrarian or sharper-take angle on a different trend.
- Post 3: a CALLBACK — connect the older concept to a current one, framed as "I said this 6 months ago, here's what just changed".

Each post must:
- Be platform-agnostic but feel native to LinkedIn (250-400 chars).
- Open with a hook, not "Excited to share".
- End with a question or sharp claim, not a list of hashtags.
- Cite at least one concept from the context (concept_id list in JSON).
- Stay honest: do not invent statistics. If no number is available, don't make one up.

Return ONLY JSON of the form:
{
  "digest": "2-3 sentence summary of what's happening this period.",
  "posts": [
    {
      "headline": "...",
      "body": "...",
      "rationale": "Why this should land.",
      "concept_ids": [1, 2],
      "source_ids": [3, 4],
      "callback_to": null
    }
  ]
}"""


def gather_context(top_n: int = 6) -> dict:
    profile = db.get_user_profile()
    if not profile:
        return {"error": "no user profile — run scripts/seed.py or set one up in the web UI"}
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name, momentum FROM concepts
            WHERE archived = 0 ORDER BY momentum DESC LIMIT ?
        """, (top_n,))
        top = [dict(r) for r in cur.fetchall()]
        for c in top:
            cur.execute("""
                SELECT c.text, r.url, s.id AS source_id
                FROM claims c
                JOIN claim_concepts cc ON cc.claim_id = c.id
                JOIN raw_items r ON r.id = c.raw_item_id
                JOIN sources s ON s.id = r.source_id
                WHERE cc.concept_id = ? AND c.valid_to IS NULL
                ORDER BY c.created_at DESC LIMIT 4
            """, (c["id"],))
            c["evidence"] = [dict(x) for x in cur.fetchall()]

        # Pick a 'callback' concept: was hot >30d ago and just reappeared
        cur.execute("""
            SELECT id, name, momentum FROM concepts
            WHERE archived = 0 AND momentum > 0.05
              AND julianday('now') - julianday(first_seen_at) > 30
              AND julianday('now') - julianday(last_seen_at) < 7
            ORDER BY momentum DESC LIMIT 1
        """)
        cb = cur.fetchone()
        callback = dict(cb) if cb else None
    return {"profile": profile, "top_concepts": top, "callback": callback}


def generate_suggestions() -> dict:
    ctx = gather_context()
    if "error" in ctx:
        return ctx

    user_payload = {
        "user": {
            "name": ctx["profile"]["name"],
            "role": ctx["profile"]["role"],
            "company": ctx["profile"].get("company"),
            "bio": ctx["profile"]["bio"],
            "interests": ctx["profile"]["interests"],
            "voice_notes": ctx["profile"].get("voice_notes") or "",
        },
        "top_concepts": ctx["top_concepts"],
        "callback_concept": ctx["callback"],
    }

    try:
        raw = llm.complete(SUGGESTION_PROMPT,
                           json.dumps(user_payload, indent=2),
                           model=config.WRITER_MODEL,
                           max_tokens=1500,
                           temperature=0.6)
        data = llm.parse_json(raw)
    except llm.NotConfigured:
        return {"needs_llm": True, "system": SUGGESTION_PROMPT,
                "user": json.dumps(user_payload, indent=2),
                "context": ctx,
                "hint": "Cowork mode — the session should write the suggestions itself, then call scripts/save_suggestion.py for each post."}
    except Exception as e:
        db.log_audit("suggest_error", f"suggestion generation failed: {e}")
        return {"error": str(e)}

    posts = data.get("posts") or []
    persisted = []
    for p in posts:
        sid = save_post(
            p.get("headline", ""),
            p.get("body", ""),
            p.get("rationale", ""),
            concept_ids=p.get("concept_ids") or [],
            source_ids=p.get("source_ids") or [],
            callback_to=p.get("callback_to"),
        )
        p["id"] = sid
        persisted.append(p)

    digest = data.get("digest", "")
    db.log_audit("suggest", f"Generated {len(persisted)} posts", {"digest": digest})
    return {"digest": digest, "posts": persisted}


def save_post(headline: str, body: str, rationale: str,
             concept_ids: list[int] | None = None,
             source_ids: list[int] | None = None,
             callback_to: str | None = None,
             kind: str | None = None) -> int:
    """Persist a single suggestion. Used by both direct mode and Cowork mode."""
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO suggestions
            (kind, headline, body, rationale, concept_ids, source_ids, callback_to)
            VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id
        """, (
            kind or ("callback" if callback_to else "post"),
            (headline or "")[:200],
            body or "",
            rationale or "",
            json.dumps(concept_ids or []),
            json.dumps(source_ids or []),
            callback_to,
        ))
        return cur.fetchone()[0]
