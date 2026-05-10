"""Orchestrate: pull from sources -> dedupe -> extract -> write claims/concepts."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Iterable

from . import db, config, llm
from .sources import FETCHERS
from .extractor import extract


def _hash(item: dict) -> str:
    payload = (item.get("title", "") + "|" + item.get("url", "") + "|" + (item.get("body") or "")[:500])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _upsert_concept(cur: sqlite3.Cursor, name: str) -> int:
    cur.execute("SELECT id, occurrences FROM concepts WHERE name = ? COLLATE NOCASE", (name,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE concepts SET occurrences = occurrences + 1, last_seen_at = datetime('now') WHERE id = ?",
            (row[0],),
        )
        return row[0]
    cur.execute(
        "INSERT INTO concepts (name, occurrences) VALUES (?, 1) RETURNING id",
        (name,),
    )
    return cur.fetchone()[0]


def ingest_source(source_id: int, kind: str, handle: str, limit: int,
                 *, run_extraction: bool | None = None) -> dict:
    """Returns counts: fetched, inserted, skipped, claims_added, concepts_touched.

    run_extraction defaults to True in anthropic/openai mode and False in cowork mode
    (where the session does extraction itself and calls save_extraction.py).
    """
    if run_extraction is None:
        run_extraction = (llm.PROVIDER != "cowork")
    fetcher = FETCHERS[kind]
    items = fetcher(handle, limit=limit)
    counts = {"fetched": len(items), "inserted": 0, "skipped": 0,
              "claims_added": 0, "concepts_touched": 0, "errors": 0}
    if not items:
        return counts

    conn = db.connect()
    cur = conn.cursor()
    try:
        for item in items:
            content_hash = _hash(item)
            # skip exact dedup by hash globally
            cur.execute("SELECT id FROM raw_items WHERE content_hash = ?", (content_hash,))
            if cur.fetchone():
                counts["skipped"] += 1
                continue
            try:
                cur.execute("""
                    INSERT INTO raw_items (source_id, external_id, title, url, body, score, posted_at, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                """, (
                    source_id, item["external_id"], item["title"], item.get("url"),
                    item.get("body") or "", item.get("score") or 0,
                    item.get("posted_at"), content_hash,
                ))
                raw_id = cur.fetchone()[0]
            except sqlite3.IntegrityError:
                counts["skipped"] += 1
                continue
            counts["inserted"] += 1

            if not run_extraction:
                # Cowork mode: leave raw item pending for the session to extract.
                continue

            # Extract via configured LLM
            extracted = extract(item.get("title", ""), item.get("body", ""), item.get("url"))
            if extracted.get("skip") or extracted.get("needs_llm"):
                continue
            for claim in extracted["claims"]:
                cur.execute("""
                    INSERT INTO claims (raw_item_id, text, stance, confidence)
                    VALUES (?, ?, ?, ?) RETURNING id
                """, (raw_id, claim["text"], claim["stance"], claim["confidence"]))
                claim_id = cur.fetchone()[0]
                counts["claims_added"] += 1
                for concept_name in extracted["concepts"]:
                    cid = _upsert_concept(cur, concept_name)
                    counts["concepts_touched"] += 1
                    try:
                        cur.execute("INSERT INTO claim_concepts (claim_id, concept_id) VALUES (?, ?)",
                                    (claim_id, cid))
                    except sqlite3.IntegrityError:
                        pass

        cur.execute("UPDATE sources SET last_fetch_at = datetime('now') WHERE id = ?", (source_id,))
    finally:
        conn.close()

    db.log_audit(
        "ingest",
        f"{kind}:{handle} → {counts['inserted']} new, {counts['claims_added']} claims",
        counts,
    )
    return counts


def ingest_all() -> list[dict]:
    """Run ingestion for every enabled source."""
    out = []
    with db.cursor() as cur:
        cur.execute("SELECT * FROM sources WHERE enabled = 1")
        sources = [dict(r) for r in cur.fetchall()]
    for s in sources:
        if s["kind"] not in FETCHERS:
            continue
        try:
            res = ingest_source(s["id"], s["kind"], s["handle"], config.INGEST_LIMIT_PER_SOURCE)
            res["source"] = f"{s['kind']}:{s['handle']}"
            out.append(res)
        except Exception as e:
            db.log_audit("ingest_error", f"{s['kind']}:{s['handle']} failed", {"error": str(e)})
            out.append({"source": f"{s['kind']}:{s['handle']}", "error": str(e)})
    return out
