"""Bluesky via the public AppView search API — no auth required for searchPosts.

Handle: a search query, e.g. 'AI agents', 'fundraising', 'b2b sales'.
"""
from __future__ import annotations
import httpx


API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def fetch(handle: str, limit: int = 25) -> list[dict]:
    query = handle.strip()
    if not query:
        return []
    params = {"q": query, "limit": min(limit, 100), "sort": "top"}
    with httpx.Client(timeout=20.0) as client:
        data = client.get(API, params=params).json()
    items: list[dict] = []
    for post in data.get("posts", []):
        record = post.get("record", {})
        items.append({
            "external_id": post.get("uri") or "",
            "title": (record.get("text") or "").split("\n")[0][:200],
            "url": _post_url(post),
            "body": record.get("text") or "",
            "score": int(post.get("likeCount") or 0) + int(post.get("repostCount") or 0),
            "posted_at": record.get("createdAt") or "",
        })
    return items


def _post_url(post: dict) -> str:
    uri = post.get("uri", "")
    handle = post.get("author", {}).get("handle", "")
    # at://did:plc:xxx/app.bsky.feed.post/RKEY → https://bsky.app/profile/<handle>/post/<rkey>
    if "/" not in uri:
        return ""
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"
