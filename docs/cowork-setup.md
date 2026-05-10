# Wiring Signal Brain into Claude Cowork

Signal Brain runs entirely on your machine. To make it *autonomous*, register a
Claude Cowork **scheduled task** that runs one cycle on an interval.

The fastest path is `/setup` — it'll do all of this for you. The rest of this
doc is for when you want to do it by hand or troubleshoot.

## What gets scheduled

The scheduled task is a **Claude prompt**, not a shell command. The prompt is
the contents of `.claude/commands/cycle.md`. The Cowork session that runs it is
itself the agent's brain — it walks the cycle steps using bash, doing the
extraction / healing / drafting in-conversation. **No API key billed to you.**

(In `anthropic` or `openai` mode, you can instead schedule the shell command
`cd /path/to/HourglassChallenge && .venv/bin/python scripts/run_all.py` —
that's a self-driving variant that uses your own API key.)

## Option A — ask Claude to set it up

In a Claude Cowork session, paste:

> Use the schedule skill to register a scheduled task that runs the contents of
> `.claude/commands/cycle.md` every 4 hours. Name it "Signal Brain — refresh".

Claude will invoke its `schedule` skill and register the task. Verify with
`mcp__scheduled-tasks__list_scheduled_tasks` or by asking "list my scheduled
tasks".

## Option B — set it up by hand

1. Open Claude Cowork.
2. Go to **Scheduled tasks** in the side menu.
3. Click **New scheduled task**.
4. Fill in:
   - **Name:** `Signal Brain — refresh`
   - **Interval:** every 4 hours (or daily)
   - **Type:** Claude prompt (not shell command)
   - **Body:** copy the full contents of `.claude/commands/cycle.md`
5. Save.

## Recommended cadence

| Cadence              | Why                                                        |
| -------------------- | ---------------------------------------------------------- |
| Every 4 hours        | Best balance — fresh signals, manageable API spend.        |
| Daily morning        | Cheapest. You see your digest with morning coffee.         |
| Hourly               | Only if you want to react to news in near-real-time.       |

## How fetching works in Cowork mode

The Cowork sandbox's outbound HTTP proxy blocks most public APIs by default —
running `httpx.get('https://...')` from a sandbox bash call mostly returns 403.
This means the legacy `scripts/fetch.py` (which does direct httpx calls) does
not work in Cowork mode.

The cycle prompt (`.claude/commands/cycle.md`) handles this by using Claude's
own **WebFetch** tool for the fetch step instead of `fetch.py`. WebFetch has a
much wider allowlist and is the right network layer for an LLM-driven agent.
The cycle:

1. Calls `python3 scripts/list_sources.py` to get each enabled source's
   `fetch_url` and `format`.
2. Calls `WebFetch` on each `fetch_url` with a prompt to extract recent items
   as JSON.
3. Calls `python3 scripts/save_raw_item.py` for each new item (content-hash
   dedup makes re-runs safe).

`scripts/fetch.py` remains for direct-API mode, where the host venv has
unrestricted network access.

## Cost note

In **Cowork mode (default):** zero direct API spend — the cycle uses your
existing Cowork session.

In `anthropic` or `openai` mode: each cycle calls a small model for extraction
(cheap) and a stronger model for suggestion-writing (one call per cycle). At
default settings (25 items per source, 5 sources) a daily run is well under
$0.10/day.

## Verifying it's working

After a cycle has run:

- `http://localhost:8787/` — top trends should populate.
- `http://localhost:8787/audit` — you should see `ingest`, `decay`,
  `merge_concepts` (if any duplicates were detected), and `suggest` events.
- `http://localhost:8787/suggestions` — drafts ready to accept/reject.

Accept/reject feedback loops back into source reliability scores — see
`signal_brain/healing.py::apply_feedback`.
