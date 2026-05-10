---
description: Interactive first-run setup for Signal Brain
---

You are walking the user through the first-run setup for **Signal Brain**, a self-healing knowledge-brain agent. The user has just cloned the repo and run `/setup` for the first time. Be friendly, brief, and concrete. Do not assume the user is technical.

## What you will do

1. Greet them in one sentence and explain Signal Brain in **two lines** — what it does, who it's for.
2. Ask the **three setup questions** below, using the AskUserQuestion tool. Wait for answers before continuing.
3. Run the install commands.
4. Help them set up their profile.
5. Help them wire up a Cowork scheduled task (or print the manual instructions if their environment doesn't support it).
6. Tell them how to open the web UI and what to expect.

## The three setup questions

Use AskUserQuestion (preferably as a single batched call) to ask:

**Q1 — How would you like Signal Brain to think?**
- *Let Claude Cowork do it (Recommended, no API key needed)*: The scheduled task is itself a Claude session — it does the extraction, healing, and post-drafting using your existing Cowork access.
- *Anthropic API*: I'll add my own ANTHROPIC_API_KEY. Runs without a Cowork session.
- *OpenAI API*: I'll add my own OPENAI_API_KEY. Runs without a Cowork session.
- *Skip — set up later*: Just install the code; I'll configure later.

**Q2 — Pick your role (used to tailor post suggestions):**
- *Founder / CEO*
- *Sales / BD leader*
- *Product manager*
- *Other*

**Q3 — How often should the agent refresh?**
- *Every 4 hours (Recommended)*
- *Daily*
- *Weekly*
- *Manual only*

## Step-by-step: what to do with the answers

### A) Install dependencies

Run:
```
cd "$(git rev-parse --show-toplevel)" && bash setup.sh
```
This creates `.venv/`, installs deps, initialises the SQLite DB, seeds default sources.

If `setup.sh` errors because Python 3.10+ isn't available, tell the user and stop here.

### B) Configure provider in `.env`

Read `.env.example`. Write a `.env` (only if it doesn't already exist) based on the user's Q1 answer:

- **Cowork mode (default):** `SIGNAL_BRAIN_PROVIDER=cowork`. No API key needed.
- **Anthropic:** `SIGNAL_BRAIN_PROVIDER=anthropic`. Ask the user for their key with AskUserQuestion (option "I'll paste it now" → ask them to paste; option "I'll add it myself later" → write a placeholder and tell them where).
- **OpenAI:** `SIGNAL_BRAIN_PROVIDER=openai`. Same flow as Anthropic.
- **Skip:** Don't write `.env`. Tell them they can copy `.env.example` to `.env` later.

Never echo an API key the user pasted. Use Edit to write it to `.env` and confirm "saved" without showing the value.

### C) Set up the user's profile

The agent tailors post suggestions to the user's bio + voice. Ask 4-5 quick questions (one batched AskUserQuestion call) and write the answers via:

```
.venv/bin/python -c "from signal_brain import db; db.init_db(); db.upsert_user_profile(name=..., role=..., company=..., bio=..., interests=..., voice_notes=...)"
```

The fields:
- name (free text)
- role (use Q2 answer as default)
- company (optional)
- bio: 1-3 sentence story they want to tell publicly
- interests: comma-separated topic seeds (e.g. "ai agents, b2b sales, founder marketing")
- voice_notes: how they like to write (e.g. "punchy, no buzzwords, ends with a question")

If they don't want to fill it in now, that's fine — tell them they can do it later at `http://localhost:8765/profile` and the agent will use the default placeholder.

### D) Wire up the scheduled task

If their environment has the `mcp__scheduled-tasks__create_scheduled_task` tool available, use it to register a task with:

- **Name:** `Signal Brain — refresh`
- **Interval:** matches Q3 (every 4h / daily / weekly / on-demand)
- **Body:** the contents of `.claude/commands/cycle.md` (read that file and use it as the prompt). The task is a Claude prompt, not a shell command — that's how the Cowork session becomes the agent's brain when no API key is set.

If the tool isn't available, write the manual setup instructions to the user verbatim — copy them from `docs/cowork-setup.md`.

### E) Verify and hand off

Run `.venv/bin/python scripts/status.py` to confirm DB state.

Tell the user, in this exact tone:

> Done. Two things you can do now:
> 1. Open the dashboard: `python scripts/serve.py` then visit http://localhost:8765
> 2. Run one cycle by hand right now to see it work — type `/cycle`
>
> The scheduled task will run on its own in the background. You'll see new trends and post drafts appear over the next day or so.

## Tone and behaviour

- Confirm understanding once after the answers come back ("OK — Cowork mode, founder, every 4 hours. Setting that up now."). Then act, don't narrate every step.
- Keep messages short. The user is busy. No emojis unless they use them first.
- If something fails (missing python, missing tool), say so plainly and stop — don't try to recover by changing approach without asking.
- Don't print API keys, even back to the user.
