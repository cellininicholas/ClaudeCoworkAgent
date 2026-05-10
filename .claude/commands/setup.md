---
description: Interactive first-run setup for Signal Brain — runs entirely in Cowork, no terminal needed
---

You are setting up **Signal Brain** for a Cowork user. Your job is to do everything yourself via the available tools — bash, Edit, AskUserQuestion. The user should not need to open a terminal at any point. Be brief, confirm once, then act.

## Constraints you must respect

- **Don't ask the user to run shell commands.** Run them yourself with `mcp__workspace__bash`. The repo is mounted in the sandbox; everything works.
- **Don't create a venv.** In Cowork mode the host never executes Python — the sandbox does. (If the user picks Anthropic or OpenAI mode, then they will need a venv on the host, and you should tell them so.)
- **Don't print API keys.** If they paste one, write it to `.env` via Edit and confirm "saved" without echoing the value.

## Step 1 — One-line greeting + ask the questions

Start with one sentence: "I'll set up Signal Brain for you. Three quick questions."

Then call `AskUserQuestion` with all three at once:

**Q1 — How should Signal Brain think?**
- *Cowork (Recommended, no API key)*: This Cowork session is the LLM. Scheduled tasks run as Claude prompts.
- *Anthropic API*: I'll add my own ANTHROPIC_API_KEY.
- *OpenAI API* (or OpenAI-compatible): I'll add my own OPENAI_API_KEY.

**Q2 — Pick your role:**
- *Founder / CEO*
- *Sales / BD leader*
- *Product manager*
- *Other*

**Q3 — How often should the agent refresh?**
- *Every 4 hours (Recommended)*
- *Daily*
- *Weekly*
- *Manual only*

After answers come back, confirm in one line ("OK — Cowork mode, founder, every 4h. Setting up.") and proceed without asking again.

## Step 2 — Initialise the database (sandbox bash)

```
mcp__workspace__bash:
cd /sessions/<session>/mnt/HourglassChallenge && python3 scripts/init_db.py
```

Replace `<session>` by reading the actual repo mount path. If you don't know the session path, run `pwd` first or use `git rev-parse --show-toplevel` from any bash call to find it.

This creates `data/signal.db`, applies the schema, and seeds default sources. Idempotent.

## Step 3 — Write `.env`

Read `.env.example`. Use the Edit tool to write a new `.env` based on Q1:

- **Cowork:** `SIGNAL_BRAIN_PROVIDER=cowork`. Leave key fields blank. Done.
- **Anthropic:** `SIGNAL_BRAIN_PROVIDER=anthropic`. Use AskUserQuestion: "Paste your ANTHROPIC_API_KEY now, or set it later?" → if pasted, Edit `.env` to set the key (don't echo it back). If later, leave blank and tell them where.
- **OpenAI:** Same pattern with `OPENAI_API_KEY`.

If they picked an API mode, also tell them: "Heads-up: API mode needs a host-side venv. Once you're back in your terminal, run `./setup.sh` once. Cowork mode doesn't need this."

## Step 4 — Profile

Ask 4–5 quick free-text questions (use AskUserQuestion with "Other" so the user types) — name, company (optional), bio (1-3 sentences), interests (comma-separated topics), voice notes (1 line on tone). Use Q2 for the role.

Save with sandbox bash:

```
cd <repo> && python3 -c "
from signal_brain import db
db.init_db()
db.upsert_user_profile(name='...', role='...', company=None, bio='...', interests='...', voice_notes='...')
print('profile saved')
"
```

If they don't want to fill it in now, that's fine. Skip and tell them they can ask you to update it any time.

## Step 5 — Schedule the cycle (Cowork mode only)

If they picked Cowork mode AND `mcp__scheduled-tasks__create_scheduled_task` is available:

- Read `.claude/commands/cycle.md` and use its full contents as the task body.
- Call the tool with: name="Signal Brain — refresh", interval matching Q3 (every 4h / daily / weekly / on-demand), body=cycle.md contents.
- If the tool isn't available, paste the manual instructions from `docs/cowork-setup.md`.

If they picked Anthropic/OpenAI mode, skip scheduling for now and tell them: "Once your venv is set up, the same scheduled task can run `./.venv/bin/python scripts/run_all.py` instead of the Claude prompt."

## Step 6 — Run one cycle right now (proof it works)

In Cowork mode, run the cycle yourself: invoke `/cycle` (you can do this directly — it's another slash command in this repo). The user will see the agent work end-to-end before the scheduled task even fires.

If you can't invoke another slash command directly, just run the cycle steps inline using bash (the steps are documented in `.claude/commands/cycle.md`).

## Step 7 — Hand off

Tell the user, in one short paragraph:

> Done. Your agent is set up and the first cycle just ran — you should see trends and post drafts above. The scheduled task will refresh every <interval> from now on. To check progress any time, just ask me ("how's my agent doing?") and I'll run a status report. If you want a visual dashboard, you can run `./setup.sh && .venv/bin/python scripts/serve.py` in your terminal — but it's optional.

## What NOT to do

- Don't tell the user to open a terminal unless they explicitly chose API mode (where the venv is required).
- Don't run `./setup.sh` yourself in the sandbox — the venv it would create is Linux-only and unusable on the user's Mac. The DB init step (step 2) is all you actually need for Cowork mode.
- Don't claim the agent ran if it didn't. If a step errored, say so plainly.
