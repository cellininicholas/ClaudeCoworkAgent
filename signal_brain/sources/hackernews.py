"""Hacker News via the public Firebase API. No auth, no rate-limit concerns at this scale.

Handle: one of 'top', 'best', 'new'. Default 'top'.
"""
from __future__ import annotations
import datetime as dt
import httpx

API = "https://hacker-news.firebaseio.com/v0"


def fetch(handle: str, limit: int = 25) -> list[dict]:
    feed = handle.strip().lower() or "top"
    if feed not in ("top", "best", "new"):
        feed = "top"
    with httpx.Client(timeout=20.0) as client:
        ids = client.get(f"{API}/{feed}stories.json").json()[:limit]
        items: list[dict] = []
        for hn_id in ids:
            try:
                d = client.get(f"{API}/item/{hn_id}.json").json()
            except Exception:
                continue
            if not d:
                continue
            posted_at = dt.datetime.fromtimestamp(d.get("time", 0), dt.timezone.utc).isoformat()
            items.append({
                "external_id": str(d.get("id")),
                "title": d.get("title") or "",
                "url": d.get("url") or f"https://news.ycombinator.com/item?id={d.get('id')}",
                "body": d.get("text") or "",
                "score": int(d.get("score") or 0),
                "posted_at": posted_at,
            })
        return items
