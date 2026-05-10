# CLAUDE.md

Instructions for Claude (in Claude Code, Claude Cowork, or any Claude-driven session) when working in this repository.

## What this project is

**Signal Brain** is a self-healing knowledge-brain agent. It ingests posts and articles from social/news sources, extracts atomic claims and concepts into a SQLite knowledge base, runs a self-healing audit pass on a schedule, and drafts post ideas tailored to the user's voice — including callbacks to older trends that are re-emerging.

Submission for the Hourglass AI agent challenge (knowledge-brain track), May 2026.

## Two ways the agent runs

1. **Cowork-managed mode (default).** No API key required, **no host setup required.** The host machine never executes Python — the Cowork sandbox does, against the SQLite DB in the mounted project folder. The agent's "brain" *is* the Claude Cowork scheduled-task session. You (Claude) drive the cycle by calling atomic bash scripts. See "Running a cycle in Cowork mode" below.
2. **Direct-API mode.** Set `SIGNAL_BRAIN_PROVIDER=anthropic` (or `openai`) and an API key. Requires a host venv (`./setup.sh`). Then `python scripts/run_all.py` does the full cycle without any Cowork session. Optional.

The selection lives in `.env` and is read by `signal_brain/llm.py`.

The dashboard is a Cowork **live artifact** (`/view` creates it; HTML lives at `signal_brain/dashboard_template.html`). The artifact calls `mcp__workspace__bash` to run the read-only `list_*.py` scripts on each open, so it always reflects current state. `/status` is a chat-only fallback. The legacy FastAPI dashboard (`scripts/serve.py`) still works but is no longer the primary surface.

## Running a cycle in Cowork mode

When invoked as a scheduled task (or by the user via `/cycle`), do these steps in order. Read each step's stdout before moving on. **The full prompt lives in `.claude/commands/cycle.md` — keep that and this section in sync.**

1. **Fetch new items via the WebFetch tool** (NOT `scripts/fetch.py`).
   Why: the Cowork sandbox's outbound proxy 403s most public APIs. WebFetch has a wider allowlist and is the right network layer for Cowork mode.
   - Run `python3 scripts/list_sources.py` to get `[{id, kind, handle, fetch_url, format}, ...]`.
   - For each, call `WebFetch(url=fetch_url, prompt="extract recent items as JSON: external_id, title, url, body, posted_at, score")`.
   - For each item, call `python3 scripts/save_raw_item.py --source-id N --json '{...}'`. Hash-dedup is built in.
   The legacy `scripts/fetch.py` still exists for direct-API mode (where the host venv has unrestricted network).

2. **List pending items needing extraction.**
   `.venv/bin/python scripts/list_pending.py --limit 20`
   Returns a JSON array. For each item, run the extraction prompt yourself (the prompt is in `signal_brain/extractor.py::EXTRACTION_PROMPT`). The expected output JSON shape is documented at the top of that file.

3. **Save each extraction.**
   `.venv/bin/python scripts/save_extraction.py --raw-id N --json '{...}'`
   Or pipe via `--stdin`. The script normalises and persists claims + concepts.

4. **Run the non-LLM healing pass.**
   `.venv/bin/python scripts/heal_basic.py`
   Recomputes momentum, archives stale concepts, applies feedback nudges.

5. **Concept-merge pass (LLM).**
   `.venv/bin/python scripts/list_concepts.py --limit 40`
   Apply the prompt in `signal_brain/healing.py::MERGE_PROMPT`. Submit any merges with `scripts/save_merge.py --json '{"merges":[...]}'`. If nothing should merge, skip.

6. **Contradiction pass (LLM).**
   `.venv/bin/python scripts/list_concepts.py --with-claims --limit 10`
   For each concept with ≥2 active claims, apply `CONTRA_PROMPT`. For each detected contradiction, decide which claim wins (higher source reliability, then more recent), then `scripts/save_supersede.py --loser X --winner Y --concept "..." --reason "..."`.

7. **Generate post drafts.**
   `.venv/bin/python scripts/suggest_context.py`
   This prints the user profile, top concepts, the optional callback concept, and the system prompt. Apply that prompt to draft 3 posts (one current trend, one contrarian, one callback). Save each with `scripts/save_suggestion.py --json '{...}'`.

8. **Show summary.**
   `.venv/bin/python scripts/status.py`

If any step fails, write a short note to `audit_log` via the existing scripts and continue.

## Code conventions

- Python ≥3.10. No new heavy deps. Stdlib + the few packages already in `requirements.txt`.
- All persistence flows through `signal_brain/db.py`. Don't open SQLite connections elsewhere.
- LLM calls go through `signal_brain/llm.py::complete`. If you add a step that needs LLM, branch on `llm.PROVIDER == "cowork"` and expose a corresponding atomic save script.
- Every self-healing or LLM action gets an entry in `audit_log` (`db.log_audit`). The user reads this in the web UI to see what the agent did.
- Don't fetch URLs outside the configured sources. Don't write to social platforms. Drafts stay drafts.

## What NOT to do

- Don't introduce vector embeddings. Concept clustering is intentionally LLM-driven for the current scale.
- Don't auto-publish, auto-DM, or send any external messages. Suggestions are local drafts.
- Don't store API keys in the repo. They live in `.env`, gitignored.
- Don't widen the schema without updating `schema.sql` AND adding a migration block in `db.py::init_db` (currently CREATE IF NOT EXISTS — fine for additive changes, NOT fine for column drops).

## Project skills (slash commands)

The project ships four Markdown skills in `.claude/commands/`. Users can invoke them either as slash commands (`/setup`) or by asking Claude in plain English ("run the setup project skill"). The plain-English form is preferred in user-facing docs because slash-command autocomplete for project-scoped commands isn't reliable in every Cowork build.

- **setup** (`/setup`) — interactive first-run setup. Walks the user through provider choice, profile creation, source config, scheduled-task wiring, and dashboard artifact. Runs entirely in Cowork — no terminal needed for Cowork mode.
- **cycle** (`/cycle`) — runs one full agent cycle (the steps above). Use this for ad-hoc runs and as the body of the Cowork scheduled task.
- **status** (`/status`) — print a status summary directly in chat. No artifact, no web server — just text.
- **view** (`/view`) — create or refresh the **signal-brain** Cowork live artifact (the dashboard). The artifact persists across sessions and pulls fresh data from `scripts/*.py` every time it's opened. This is the primary way users see their agent's state.

## File map (curated)

| Path | What |
|------|------|
| `schema.sql` | The knowledge-base schema. Provenance + temporal validity. |
| `signal_brain/llm.py` | Provider abstraction (anthropic / openai / cowork). |
| `signal_brain/extractor.py` | `EXTRACTION_PROMPT` + `normalise()` for claim extraction. |
| `signal_brain/healing.py` | All self-healing layers + `MERGE_PROMPT`/`CONTRA_PROMPT`. |
| `signal_brain/suggester.py` | `SUGGESTION_PROMPT` + `gather_context()` + `save_post()`. |
| `signal_brain/web.py` | FastAPI localhost UI. |
| `scripts/list_sources.py` | (no LLM) enabled sources + their fetch_url; `--with-counts` for the dashboard. |
| `scripts/save_raw_item.py` | persist one fetched item (Cowork mode). |
| `scripts/fetch.py` | (no LLM) pull from sources via httpx, store raw_items. Used by direct-API mode. |
| `scripts/list_suggestions.py` | recent drafts as JSON; used by the dashboard artifact. |
| `scripts/list_audit.py` | recent audit log as JSON; used by the dashboard artifact. |
| `scripts/feedback_suggestion.py` | apply accept/reject to a suggestion (called from the dashboard). |
| `signal_brain/dashboard_template.html` | the dashboard artifact's HTML. `__SB_REPO_PATH__` placeholder is substituted by `/view`. |
| `scripts/list_pending.py` | items needing extraction (JSON). |
| `scripts/save_extraction.py` | persist one extraction result. |
| `scripts/heal_basic.py` | (no LLM) decay + archive + feedback. |
| `scripts/list_concepts.py` | concepts (optionally with claims) for the audit pass. |
| `scripts/save_merge.py` | apply a merge plan. |
| `scripts/save_supersede.py` | resolve one contradiction. |
| `scripts/suggest_context.py` | context for post drafting. |
| `scripts/save_suggestion.py` | persist one drafted post. |
| `scripts/status.py` | summary JSON. |
| `scripts/run_all.py` | direct-API mode: full cycle in one process. |
| `scripts/serve.py` | start the localhost web UI. |
