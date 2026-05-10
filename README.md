# Signal Brain

A self-healing, autonomous **knowledge-brain agent** for busy founders, sales
leaders, and operators. Ingests your industry signal, builds a structured
knowledge base, and drafts post ideas in your voice — including callbacks to
trends it noticed weeks ago. Runs locally.

Built solo for the [Hourglass AI agent challenge](https://challenge.thehourglass.ai/)
(knowledge-brain track, May 2026).

## Quick start (recommended path — no API key, no terminal)

```
git clone https://github.com/cellininicholas/ClaudeCoworkAgent.git
```

Open the folder in **Claude Cowork** and type:

```
/setup
```

That's it. Cowork walks you through three questions, runs the install, sets up
your profile, registers a scheduled task, and runs the first cycle. **No
terminal, no API key, no Python venv** — the Cowork session itself is the
agent's brain.

Once running, ask Claude any time:

- `/cycle` — run one cycle now
- `/view` — open the live dashboard (a persistent Cowork artifact)
- `/status` — show a status summary in chat
- "what trends are emerging?" — Claude reads the DB and answers

The **`/view` artifact** is the main surface: a Cowork-native page that shows
trends, drafted posts (with accept/reject), sources, and the audit log of every
self-healing action. It pulls fresh data from your local SQLite every time you
open it. There's also an older FastAPI dashboard (`scripts/serve.py`) — kept
around as a fallback but no longer needed.

## What it does

1. **Ingests** from sources you pick — Hacker News, Reddit, RSS/Substack feeds,
   Bluesky search queries.
2. **Extracts** atomic *claims* and *concepts* from each item with Claude Haiku.
3. **Builds a knowledge base** in SQLite with full provenance: every claim is
   tied to its source, scored, and time-bounded (`valid_from` / `valid_to`).
4. **Self-heals** on a schedule: contradiction detection, concept merging,
   stale-trend archival, momentum decay, source-reliability nudges.
5. **Suggests** three post drafts per cycle in your voice — one ride-the-trend,
   one contrarian, one *callback* (an old trend re-emerging).
6. **Learns** from your accept/reject feedback — boosts reliability of sources
   whose signal led to accepted posts, penalises those that led to rejected ones.

## Optional: legacy FastAPI dashboard

If you want a fully-local fallback (no Cowork, just a localhost web server),
run this in your terminal:

```bash
./setup.sh                        # creates .venv, installs deps, inits DB
.venv/bin/python scripts/serve.py # http://localhost:8787
```

This duplicates what the `/view` artifact does. You don't need both — the
artifact is the primary surface in Cowork mode.

## Manual setup (if you don't want `/setup`)

```bash
./setup.sh                        # creates .venv, installs deps, inits DB
cp .env.example .env              # default provider is `cowork` — no key needed
.venv/bin/python scripts/test_sources.py
```

To run a cycle by hand inside Cowork, type `/cycle`. To run autonomously, wire
`/cycle` into a Cowork scheduled task — see [docs/cowork-setup.md](docs/cowork-setup.md).

## Two ways to run

The agent supports three providers, picked by `SIGNAL_BRAIN_PROVIDER` in `.env`:

| Mode | API key needed | How it works |
|------|----------------|--------------|
| `cowork` *(default)* | none | The scheduled Cowork task **is** the LLM. It calls atomic bash scripts to fetch and persist data, and does the extraction / healing / drafting in-conversation. |
| `anthropic` | `ANTHROPIC_API_KEY` | Direct Anthropic API. Run `python scripts/run_all.py` autonomously. |
| `openai` | `OPENAI_API_KEY` | Direct OpenAI API (or OpenAI-compatible — Together, OpenRouter, Ollama). Same `run_all.py`. |

## Architecture

```
┌──────────────┐    ┌──────────────────────┐    ┌─────────────┐
│  HN / Reddit │    │  Claude Haiku        │    │   SQLite    │
│  RSS / Bsky  │───▶│  (claim extraction)  │───▶│  raw_items  │
└──────────────┘    └──────────────────────┘    │  claims     │
                                                │  concepts   │
                    ┌──────────────────────┐    │  audit_log  │
                    │  Self-heal pass:     │◀──▶│  sources    │
                    │  - momentum decay    │    │  user_prof. │
                    │  - merge duplicates  │    └─────────────┘
                    │  - contradictions    │
                    │  - feedback uplift   │
                    └──────────────────────┘           │
                                                       ▼
                    ┌──────────────────────┐    ┌─────────────┐
                    │  Claude Sonnet       │    │  Suggestions│
                    │  (post drafting)     │───▶│  (in DB +   │
                    └──────────────────────┘    │  web UI)    │
                                                └─────────────┘
```

A single `python scripts/run_all.py` walks all three stages.

## Self-healing techniques

The "knowledge brain" track of the challenge calls for an agent that
*self-heals over time*. Signal Brain layers six independent mechanisms:

| Mechanism                       | Where                                | What it does |
| ------------------------------- | ------------------------------------ | ------------ |
| Provenance + temporal validity  | `schema.sql` (claims table)          | Every claim has `valid_from`, `valid_to`, `superseded_by`. Nothing is overwritten. |
| Source reliability scoring      | `sources.reliability` (0–1)          | Multiplied into momentum; nudged by user feedback. |
| Momentum decay                  | `healing.recompute_momentum`         | Exponential decay (7-day half-life). Old signal fades. |
| Stale-concept archival          | `healing.archive_stale`              | Concepts with low momentum + no recent claims get archived (not deleted). |
| LLM concept merger              | `healing.merge_duplicate_concepts`   | Claude scans top concepts, finds aliases ("ai agents" / "agentic ai") and merges. |
| LLM contradiction detector      | `healing.detect_contradictions`      | Per concept, finds claim pairs with opposing stance; supersedes the lower-reliability one. |
| Feedback-driven reliability     | `healing.apply_feedback`             | Accepting a suggestion boosts the sources it cited; rejecting it penalises them. |

Every action is written to `audit_log` so the user can read exactly what the
agent did and why — visible at `http://localhost:8787/audit`.

## Project layout

```
signal_brain/
  config.py            # env + tunables
  db.py                # SQLite helpers, audit logger
  llm.py               # provider abstraction (anthropic / openai / cowork)
  sources/             # one file per source kind (hackernews, reddit, rss, bluesky)
  extractor.py         # claim/concept extraction (prompt + normalise)
  ingest.py            # orchestrator (run_extraction toggle for Cowork mode)
  healing.py           # self-healing layers (LLM-required steps skip in Cowork mode)
  suggester.py         # post drafts (callback-aware)
  web.py               # FastAPI UI
  templates/           # Jinja2 templates (Tailwind via CDN)
schema.sql             # SQLite schema with provenance + temporal validity
scripts/
  init_db.py           # init + seed default sources
  fetch.py             # (no LLM) pull from sources, store raw_items
  list_pending.py      # raw items needing extraction (JSON)
  save_extraction.py   # persist one extraction result
  heal_basic.py        # (no LLM) decay + archive + feedback
  list_concepts.py     # concepts (optionally with claims) for audit pass
  save_merge.py        # apply a concept-merge plan
  save_supersede.py    # resolve one contradiction
  suggest_context.py   # context for post drafting
  save_suggestion.py   # persist one drafted post
  status.py            # quick state summary
  run_all.py           # direct-API mode: full cycle in one process
  serve.py             # localhost web UI
  test_sources.py      # network sanity check
.claude/commands/
  setup.md             # /setup — interactive first-run setup
  cycle.md             # /cycle — one full agent cycle (used by scheduled task)
CLAUDE.md              # instructions for any Claude session working in this repo
docs/
  cowork-setup.md      # how to wire /cycle into a Cowork scheduled task
```

## Sources & why these

| Source       | Auth        | Cost | Why for business audience                |
| ------------ | ----------- | ---- | ---------------------------------------- |
| Hacker News  | none        | free | Where tech/startup signal surfaces first |
| Reddit       | none (read) | free | Pick subs that match your audience       |
| RSS/Substack | none        | free | The newsletters thoughtful operators read |
| Bluesky      | none (read) | free | Open social-media signal, X-replacement   |
| ~~X/Twitter~~| paid + auth | $$   | Dropped: friction-to-value ratio is bad  |
| ~~LinkedIn~~ | gated       | n/a  | Dropped: no public posts API; scraping is ToS-risky |

You can add or remove sources at `http://localhost:8787/sources`.

## What it doesn't do (yet)

- No vector embeddings; concept clustering is LLM-driven instead. Cheaper and
  good enough at this scale; if the corpus grew past ~10k claims you'd want
  embeddings + drift detection.
- No multi-user; profile is single-row.
- No write access to LinkedIn/X/Bluesky — drafts are *drafts*. You hit publish.

## License

MIT.
