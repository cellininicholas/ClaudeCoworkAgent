"""Information extraction: turn a raw item into atomic claims + concepts.

Output schema (JSON):
{
  "skip": false,                   // true if low-signal/spam/off-topic
  "claims": [
    {"text": "...", "stance": "positive|negative|neutral", "confidence": 0..1}
  ],
  "concepts": ["..."]              // short canonical noun phrases
}

In Anthropic/OpenAI mode this calls the LLM directly. In Cowork-managed mode it
returns a "needs_llm" stub — the Cowork session is expected to do the extraction
itself (its system prompt is below as EXTRACTION_PROMPT) and call
`scripts/save_extraction.py` with the result.
"""
from __future__ import annotations
from typing import Any

from . import llm


EXTRACTION_PROMPT = """You are an information-extraction component of a knowledge-brain agent.
Read one piece of content (a post, article headline, comment) and extract:
- Atomic CLAIMS: factual or opinion statements that could later be verified or contradicted.
  Each claim must be self-contained (no pronouns referring to the source).
  Stance: 'positive' (something is happening / works / is good), 'negative' (declining / broken / bad), 'neutral'.
- CONCEPTS: 1-5 short canonical noun phrases that this item is about. Lowercase. No years. No vague terms like "things" or "stuff".

Quality rules:
- If the item is spam, off-topic clickbait, low-signal meme, NSFW, or incoherent, set skip=true and return empty arrays.
- Prefer 1-3 sharp claims over many weak ones. Skip purely procedural content (job postings, "show HN: my project", sponsored posts).
- Concepts should be the kind a busy founder/sales leader would want to track over weeks: techniques, markets, tools, behaviours, regulations.

Return ONLY a JSON object. No prose, no code fences."""


def extract(title: str, body: str, url: str | None = None) -> dict[str, Any]:
    """Returns {"skip": bool, "claims": [...], "concepts": [...]} or
    {"needs_llm": True, "prompt": ...} in Cowork mode.

    Resilient: on any error returns a skip stub.
    """
    user = f"TITLE: {title}\nURL: {url or ''}\nBODY: {(body or '')[:4000]}"
    try:
        raw = llm.complete(EXTRACTION_PROMPT, user, max_tokens=600)
    except llm.NotConfigured:
        return {"needs_llm": True, "system": EXTRACTION_PROMPT, "user": user}
    except Exception as e:
        return {"skip": True, "claims": [], "concepts": [], "_error": str(e)}
    return normalise(llm.parse_json(raw))


def normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw extraction dict (from LLM JSON) into the canonical shape.
    Used both for direct LLM mode and for results posted by the Cowork session."""
    data.setdefault("skip", False)
    norm_claims = []
    for c in (data.get("claims") or []):
        if not isinstance(c, dict) or not c.get("text"):
            continue
        norm_claims.append({
            "text": str(c["text"]).strip()[:500],
            "stance": c.get("stance") or "neutral",
            "confidence": float(c.get("confidence") or 0.7),
        })
    data["claims"] = norm_claims
    data["concepts"] = [str(c).strip().lower()[:80]
                        for c in (data.get("concepts") or [])
                        if c and len(str(c).strip()) > 1]
    return data
