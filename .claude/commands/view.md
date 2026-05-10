---
description: Create or refresh the Signal Brain dashboard as a Cowork live artifact
---

You are creating (or refreshing) the **Signal Brain dashboard** as a Cowork live artifact. The user typed `/view`. After this, they'll be able to open the artifact any time and see live agent state, accept/reject post drafts, and audit what the agent has done.

## Steps

**1. Find the repo path.**
```
mcp__workspace__bash:
git rev-parse --show-toplevel
```
Capture this — call it `REPO_PATH`. The dashboard's HTML hardcodes it because the artifact runs in a sandboxed view that has no notion of cwd.

**2. Verify the prerequisite scripts exist.**
```
ls "$REPO_PATH"/scripts/{status.py,list_suggestions.py,list_concepts.py,list_sources.py,list_audit.py,feedback_suggestion.py}
```
If any are missing, stop and tell the user the repo seems out of sync — they should `git pull`.

**3. Render the dashboard HTML.**

Read `signal_brain/dashboard_template.html` and write a substituted version to `data/dashboard.html` with `__SB_REPO_PATH__` replaced by the absolute repo path. (Use `data/` because it's gitignored — this is per-machine state, not a committed artifact.) Use bash:
```
mkdir -p "$REPO_PATH/data"
sed "s|__SB_REPO_PATH__|$REPO_PATH|g" "$REPO_PATH/signal_brain/dashboard_template.html" > "$REPO_PATH/data/dashboard.html"
```

**4. Create or update the artifact.**

First check if it already exists:
```
mcp__cowork__list_artifacts
```

If an artifact with id `signal-brain` exists, call `mcp__cowork__update_artifact` with:
- `id`: `signal-brain`
- `html_path`: the absolute path to `$REPO_PATH/data/dashboard.html`
- `mcp_tools`: `["mcp__workspace__bash"]`
- `update_summary`: "Refreshed dashboard from latest template."

Otherwise call `mcp__cowork__create_artifact` with:
- `id`: `signal-brain`
- `description`: "Signal Brain dashboard — live agent state. Top trends, drafted posts, sources, and the audit log of every self-healing action."
- `html_path`: the absolute path to `$REPO_PATH/data/dashboard.html`
- `mcp_tools`: `["mcp__workspace__bash"]`

**5. Confirm to the user.**

> Dashboard ready. Click the **signal-brain** artifact in your Cowork sidebar — it'll fetch fresh data every time you open it. The Suggestions tab is the only place that writes back: accept/reject buttons feed source-reliability nudges into the next self-heal pass.

If `create_artifact` returns an error (e.g. forbidden tool, schema mismatch), report the error verbatim and tell the user the FastAPI dashboard (`./setup.sh && python scripts/serve.py`) is the fallback.

## Constraints

- Don't edit `signal_brain/dashboard_template.html` — that's the source of truth, the user can pull updates via git.
- Don't bake an API key into the HTML. The artifact reads only from local SQLite via `mcp__workspace__bash`.
- The repo path baked into the artifact is per-machine. If the user moves the project, ask them to run `/view` again.
