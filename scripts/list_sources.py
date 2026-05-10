"""List enabled sources with the URL the Cowork session should fetch via WebFetch.

Used by the Cowork-mode cycle: the session reads this list, calls WebFetch on
each `fetch_url`, parses the response, then calls `save_raw_item.py` for each
new item. Also used by the dashboard artifact (with --with-counts).

Output: JSON array. Each row: {id, kind, handle, label, fetch_url, format,
                               reliability, enabled, n_items?, last_fetch_at?}
- format is 'rss' (Atom/RSS feed) or 'json' (raw JSON)
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from signal_brain import db


# Maps (kind, handle) → (URL, format-hint).
# Where possible we use feeds that return clean items in a single GET, since
# WebFetch in Cowork can't easily do N+1 fetches.
def fetch_url_for(kind: str, handle: str) -> tuple[str, str]:
    k = kind.lower()
    h = (handle or "").strip()
    if k == "hackernews":
        # hnrss.org mirrors HN as RSS — single feed, no N+1.
        feed = h.lower() if h.lower() in ("frontpage", "best", "newest") else {
            "top": "frontpage", "best": "best", "new": "newest"
        }.get(h.lower(), "frontpage")
        return f"https://hnrss.org/{feed}", "rss"
    if k == "reddit":
        sub = h.lstrip("/").removeprefix("r/")
        return f"https://www.reddit.com/r/{sub}/.rss", "rss"
    if k == "rss":
        return h, "rss"
    if k == "bluesky":
        # Bluesky returns JSON. Cowork's WebFetch handles JSON fine.
        return f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={quote_plus(h)}&limit=25", "json"
    # Unknown kind — pass through and let WebFetch decide.
    return h, "rss"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-counts", action="store_true",
                   help="include n_items + last_fetch_at + reliability (used by the dashboard)")
    ap.add_argument("--all", action="store_true",
                   help="include disabled sources too (default: enabled only)")
    args = ap.parse_args()
    db.init_db()
    where = "" if args.all else "WHERE enabled = 1"
    with db.cursor() as cur:
        cur.execute(f"""
            SELECT id, kind, handle, label, enabled, reliability, last_fetch_at
            FROM sources {where} ORDER BY id
        """)
        rows = []
        for r in cur.fetchall():
            url, fmt = fetch_url_for(r["kind"], r["handle"])
            entry = {
                "id": r["id"],
                "kind": r["kind"],
                "handle": r["handle"],
                "label": r["label"],
                "fetch_url": url,
                "format": fmt,
                "enabled": bool(r["enabled"]),
                "reliability": r["reliability"],
                "last_fetch_at": r["last_fetch_at"],
            }
            if args.with_counts:
                cur.execute("SELECT COUNT(*) FROM raw_items WHERE source_id = ?", (r["id"],))
                entry["n_items"] = cur.fetchone()[0]
            rows.append(entry)
    json.dump(rows, sys.stdout, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
