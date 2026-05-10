"""Source fetchers. Each returns a list of normalized RawItem dicts.

A RawItem has: external_id, title, url, body, score, posted_at (ISO).
"""
from .hackernews import fetch as fetch_hackernews
from .reddit import fetch as fetch_reddit
from .rss import fetch as fetch_rss
from .bluesky import fetch as fetch_bluesky

FETCHERS = {
    "hackernews": fetch_hackernews,
    "reddit": fetch_reddit,
    "rss": fetch_rss,
    "bluesky": fetch_bluesky,
}
