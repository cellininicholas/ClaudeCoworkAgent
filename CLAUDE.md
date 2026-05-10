# CLAUDE.md

Instructions for Claude (in Claude Code, Claude Cowork, or any Claude-driven session) when working in this repository.

## What this project is

**Signal Brain** is a self-healing knowledge-brain agent. It ingests posts and articles from social/news sources, extracts atomic claims and concepts into a SQLite knowledge base, runs a self-healing audit pass on a schedule, and drafts post ideas tailored to the user's voice — including callbacks to older trends that are re-emerging.

Submission for the Hourglass AI agent challenge (knowledge-brain track), May 2026.

## Two ways the agent runs

1. **Cowork-managed mode (default).** No API key required, **no host setup required.** The host machine never executes Python — the Cowork sandbox does, against the SQLite DB in the mounted project folder. The agent's "brain" *is* the Claude Cowork scheduled-task session. You (Claude) drive the cycle by calling atomic bash scripts. See "Running a cycle in Cowork mode" below.
2. **Direct-API mode.** Set `SIGNAL_BRAIN_PROVIDER=anthropic` (or `openai`) and an API key. Requires a host venv (`./setup.sh`). Then `python scripts/run_all.py` does the full cycle without any Cowork session. Optional.

The selection lives in `.env` and is read by `signal_brain/llm.py`.

The web dashboard (`scripts/serve.py`) is **optional** in either mode — it's a viewer, not load-bearing. `/status` gives the same information in chat.

## Running a cycle in Cowork mode

When invoked as a scheduled task (or by the user via `/cycle`), do these steps in order. Read each step's stdout before moving on.

1. **Fetch new items.**
   `cd "$REPO" && .venv/bin/python scripts/fetch.py`
   Inserts raw_items, no LLM. Idempotent — exact-hash dedup means re-runs are safe.

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

## Slash commands

- `/setup` — interactive first-run setup. Walks the user through provider choice, profile creation, source config, and Cowork scheduled-task wiring. **Runs entirely in Cowork — no terminal needed for Cowork mode.**
- `/cycle` — runs one full agent cycle (the steps above). Use this for ad-hoc runs and as the body of the Cowork scheduled task.
- `/status` — print a Cowork-native status summary in chat. Equivalent to the dashboard, no web server required.

## File map (curated)

| Path | What |
|------|------|
| `schema.sql` | The knowledge-base schema. Provenance + temporal validity. |
| `signal_brain/llm.py` | Provider abstraction (anthropic / openai / cowork). |
| `signal_brain/extractor.py` | `EXTRACTION_PROMPT` + `normalise()` for claim extraction. |
| `signal_brain/healing.py` | All self-healing layers + `MERGE_PROMPT`/`CONTRA_PROMPT`. |
| `signal_brain/suggester.py` | `SUGGESTION_PROMPT` + `gather_context()` + `save_post()`. |
| `signal_brain/web.py` | FastAPI localhost UI. |
| `scripts/fetch.py` | (no LLM) pull from sources, store raw_items. |
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
