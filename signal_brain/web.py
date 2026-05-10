"""FastAPI localhost UI: browse trends, suggestions, sources, audit log.

Templates live in signal_brain/templates/. Tailwind via CDN, no JS bundling.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, config, ingest as ingest_mod, healing, suggester


HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

app = FastAPI(title="Signal Brain", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


# ---------- helpers ----------

def _stats() -> dict:
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw_items"); items = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM claims WHERE valid_to IS NULL"); claims = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM concepts WHERE archived = 0"); concepts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM suggestions WHERE feedback IS NULL"); pending = cur.fetchone()[0]
    return {"items": items, "claims": claims, "concepts": concepts, "pending_suggestions": pending}


# ---------- routes ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name, momentum, occurrences, last_seen_at
            FROM concepts WHERE archived = 0
            ORDER BY momentum DESC LIMIT 30
        """)
        trends = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT id, kind, headline, body, rationale, callback_to, created_at, feedback
            FROM suggestions ORDER BY created_at DESC LIMIT 6
        """)
        suggestions = [dict(r) for r in cur.fetchall()]
    return templates.TemplateResponse(request, "home.html", {
        "stats": _stats(), "trends": trends, "suggestions": suggestions,
        "profile": db.get_user_profile(),
    })


@app.get("/trends", response_class=HTMLResponse)
def trends(request: Request):
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, name, momentum, occurrences, first_seen_at, last_seen_at
            FROM concepts WHERE archived = 0
            ORDER BY momentum DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for c in rows:
            cur.execute("""
                SELECT cl.text, cl.stance, r.url, r.title
                FROM claims cl
                JOIN claim_concepts cc ON cc.claim_id = cl.id
                JOIN raw_items r ON r.id = cl.raw_item_id
                WHERE cc.concept_id = ? AND cl.valid_to IS NULL
                ORDER BY cl.created_at DESC LIMIT 3
            """, (c["id"],))
            c["evidence"] = [dict(x) for x in cur.fetchall()]
    return templates.TemplateResponse(request, "trends.html", {
        "stats": _stats(), "trends": rows,
    })


@app.get("/suggestions", response_class=HTMLResponse)
def suggestions_page(request: Request):
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, kind, headline, body, rationale, concept_ids, source_ids,
                   callback_to, created_at, feedback
            FROM suggestions ORDER BY created_at DESC LIMIT 50
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["concept_ids"] = json.loads(r["concept_ids"] or "[]")
            r["source_ids"] = json.loads(r["source_ids"] or "[]")
    return templates.TemplateResponse(request, "suggestions.html", {
        "stats": _stats(), "suggestions": rows,
    })


@app.post("/suggestions/{sid}/feedback")
def feedback(sid: int, action: str = Form(...)):
    if action not in ("accepted", "rejected"):
        return RedirectResponse("/suggestions", status_code=303)
    with db.cursor() as cur:
        cur.execute("UPDATE suggestions SET feedback = ? WHERE id = ?", (action, sid))
    db.log_audit("suggestion_feedback", f"Suggestion #{sid} {action}", {"suggestion_id": sid})
    return RedirectResponse("/suggestions", status_code=303)


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    with db.cursor() as cur:
        cur.execute("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM raw_items WHERE source_id = s.id) AS items,
                   (SELECT MAX(fetched_at) FROM raw_items WHERE source_id = s.id) AS last_item
            FROM sources s ORDER BY s.kind, s.handle
        """)
        rows = [dict(r) for r in cur.fetchall()]
    return templates.TemplateResponse(request, "sources.html", {
        "stats": _stats(), "sources": rows,
    })


@app.post("/sources/add")
def sources_add(kind: str = Form(...), handle: str = Form(...), label: str = Form("")):
    label = label or f"{kind}:{handle}"
    db.upsert_source(kind, handle, label)
    return RedirectResponse("/sources", status_code=303)


@app.post("/sources/{sid}/toggle")
def sources_toggle(sid: int):
    with db.cursor() as cur:
        cur.execute("UPDATE sources SET enabled = 1 - enabled WHERE id = ?", (sid,))
    return RedirectResponse("/sources", status_code=303)


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    with db.cursor() as cur:
        cur.execute("""
            SELECT id, action, detail, metadata, created_at
            FROM audit_log ORDER BY created_at DESC LIMIT 200
        """)
        rows = [dict(r) for r in cur.fetchall()]
    return templates.TemplateResponse(request, "audit.html", {
        "stats": _stats(), "events": rows,
    })


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    return templates.TemplateResponse(request, "profile.html", {
        "stats": _stats(), "profile": db.get_user_profile() or {},
    })


@app.post("/profile")
def profile_save(name: str = Form(...), role: str = Form(...), company: str = Form(""),
                 bio: str = Form(...), interests: str = Form(...), voice_notes: str = Form("")):
    db.upsert_user_profile(name, role, company or None, bio, interests, voice_notes or None)
    return RedirectResponse("/profile", status_code=303)


# ---------- one-click run buttons ----------

@app.post("/run/ingest")
def run_ingest():
    ingest_mod.ingest_all()
    return RedirectResponse("/", status_code=303)


@app.post("/run/heal")
def run_heal():
    healing.run_audit()
    return RedirectResponse("/audit", status_code=303)


@app.post("/run/suggest")
def run_suggest():
    suggester.generate_suggestions()
    return RedirectResponse("/suggestions", status_code=303)
