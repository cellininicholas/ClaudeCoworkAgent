---
description: Create or refresh the Signal Brain dashboard as a Cowork live artifact (snapshot baked in at creation time)
---

You are creating (or refreshing) the **Signal Brain dashboard** as a Cowork live artifact. Cowork artifacts can't call workspace bash from their JS, so we **bake the snapshot into the HTML** at creation time. To refresh, the user re-runs this skill.

Run every step below.

## Steps

**1. Find the repo path.**
```
git rev-parse --show-toplevel
```
Capture as `REPO_PATH`.

**2. Make sure the DB exists and is seeded.**
```
python3 "$REPO_PATH/scripts/init_db.py"
```
Idempotent.

**3. Verify required scripts exist.**
```
ls "$REPO_PATH"/scripts/{snapshot.py,feedback_suggestion.py}
```
If missing, the repo is out of sync — tell the user to `git pull` and stop.

**4. Get a snapshot of the agent's current state.**
```
python3 "$REPO_PATH/scripts/snapshot.py"
```
Capture stdout. It's a single JSON object containing stats, trends, suggestions, sources, audit log, and profile.

**5. Render the dashboard HTML.**
Read `signal_brain/dashboard_template.html` and substitute `__SB_SNAPSHOT__` with the snapshot JSON from step 4. Write to `data/dashboard.html`. Use bash:
```
mkdir -p "$REPO_PATH/data"
SNAPSHOT="$(python3 "$REPO_PATH/scripts/snapshot.py")"
python3 - <<PY
import os
template = open("$REPO_PATH/signal_brain/dashboard_template.html").read()
snap = os.environ["SNAP_JSON"]
out = template.replace("__SB_SNAPSHOT__", snap)
open("$REPO_PATH/data/dashboard.html", "w").write(out)
PY
```
Or simpler — pass the snapshot via env var to a one-liner Python:
```
python3 -c "
import os
t = open('$REPO_PATH/signal_brain/dashboard_template.html').read()
import sys, json
snap = json.dumps(json.loads(open('/dev/stdin').read()))
open('$REPO_PATH/data/dashboard.html','w').write(t.replace('__SB_SNAPSHOT__', snap))
" < <(python3 "$REPO_PATH/scripts/snapshot.py")
```
Either works — the goal is `data/dashboard.html` contains the template with `__SB_SNAPSHOT__` replaced by the literal JSON snapshot. Confirm with:
```
grep -c "__SB_SNAPSHOT__" "$REPO_PATH/data/dashboard.html"
```
Must return `0`.

**6. Create or update the artifact.**

Call `mcp__cowork__list_artifacts`. If `signal-brain` exists, call `mcp__cowork__update_artifact`:
- `id`: `signal-brain`
- `html_path`: `$REPO_PATH/data/dashboard.html`
- `mcp_tools`: `[]` (the artifact no longer needs any MCP tools — data is baked in)
- `update_summary`: "Refreshed snapshot."

Otherwise call `mcp__cowork__create_artifact`:
- `id`: `signal-brain`
- `description`: "Signal Brain dashboard — live agent state with self-healing audit log."
- `html_path`: `$REPO_PATH/data/dashboard.html`
- `mcp_tools`: `[]`

**7. Report state to the user.**

Read the snapshot's `stats.raw_items` and `audit` array. Pick a case:

**Case A — fresh DB, no items, no audit yet:**
> Dashboard is set up — click **signal-brain** in your Cowork sidebar. It's empty because no cycle has run yet. Ask me to **run the cycle project skill** and I'll do one full pass: fetch via WebFetch, extract claims, run self-heal layers, draft three posts. Then ask me to run the **view** project skill again to refresh this snapshot.

**Case B — has audit entries but no raw items (likely failed earlier cycles):**
> Dashboard is set up. The Audit tab shows previous cycles tried to fetch but didn't end up with usable items (likely 403s from the old fetch path). Ask me to **run the cycle project skill** for a fresh pass — current cycle uses Claude's WebFetch tool, which has a much wider allowlist. After the cycle, ask me to run the **view** project skill again to update the snapshot.

**Case C — has data:**
> Dashboard ready — click **signal-brain** in your sidebar. Snapshot has {raw_items} items, {active_claims} claims, {pending_suggestions} drafts pending. Click Accept/Reject on any draft — your choice gets sent back to me here for recording. After running another cycle, ask me to run the **view** project skill to refresh.

In every case, append:
> The dashboard's data is baked in at this moment. Re-run the **view** skill any time you want fresh numbers.

If the artifact-create call fails, paste the error verbatim and tell the user the FastAPI fallback (`./setup.sh && python scripts/serve.py`) still works.
