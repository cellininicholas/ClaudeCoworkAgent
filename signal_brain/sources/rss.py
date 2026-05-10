"""Generic RSS/Atom — works for Substack, Medium, blogs, podcast feeds, etc.

Handle: a full feed URL.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import feedparser


def fetch(handle: str, limit: int = 25) -> list[dict]:
    parsed = feedparser.parse(handle)
    items: list[dict] = []
    for entry in parsed.entries[:limit]:
        # Try multiple date fields
        posted_at = None
        for key in ("published_parsed", "updated_parsed"):
            t = entry.get(key)
            if t:
                posted_at = dt.datetime(*t[:6], tzinfo=dt.timezone.utc).isoformat()
                break
        if posted_at is None:
            posted_at = dt.datetime.now(dt.timezone.utc).isoformat()

        ext_id = entry.get("id") or entry.get("link") or hashlib.sha256(
            (entry.get("title", "") + entry.get("link", "")).encode()
        ).hexdigest()

        body = entry.get("summary") or ""
        if "content" in entry and entry.content:
            body = entry.content[0].get("value", body)

        items.append({
            "external_id": str(ext_id),
            "title": entry.get("title", "") or "",
            "url": entry.get("link", "") or "",
            "body": body,
            "score": 0,  # RSS has no score
            "posted_at": posted_at,
        })
    return items
