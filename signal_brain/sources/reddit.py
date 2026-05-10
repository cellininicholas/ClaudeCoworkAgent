"""Reddit via the public .json endpoint — no auth needed for read.

Handle: subreddit name without 'r/'. Examples: 'startups', 'sales', 'entrepreneur', 'marketing'.
"""
from __future__ import annotations
import datetime as dt
import httpx

UA = "SignalBrain/0.1 (knowledge-brain agent)"


def fetch(handle: str, limit: int = 25) -> list[dict]:
    subreddit = handle.strip().lstrip("/").removeprefix("r/")
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit={limit}"
    with httpx.Client(timeout=20.0, headers={"User-Agent": UA}) as client:
        data = client.get(url).json()
    items: list[dict] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        posted_at = dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.timezone.utc).isoformat()
        items.append({
            "external_id": d.get("id"),
            "title": d.get("title") or "",
            "url": "https://reddit.com" + (d.get("permalink") or ""),
            "body": d.get("selftext") or "",
            "score": int(d.get("score") or 0),
            "posted_at": posted_at,
        })
    return items
