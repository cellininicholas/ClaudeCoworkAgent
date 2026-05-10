---
description: Show the current state of the Signal Brain agent in Cowork — no dashboard needed
---

You are showing the user a snapshot of their Signal Brain agent's state. The user typed `/status`. Run the status script and present its output as a friendly, scannable summary in chat.

## Step 1 — Run the status script

```
cd <repo> && python3 scripts/status.py
```

This returns JSON with keys:
- `raw_items` — total items pulled from sources
- `pending_extraction` — raw items not yet extracted into claims
- `active_claims` — claims still believed (not superseded)
- `concepts` — active (non-archived) concepts
- `pending_suggestions` — drafted posts awaiting accept/reject
- `top_trends` — list of `{name, momentum}` sorted by momentum
- `recent_audit` — last 8 audit-log entries (action, detail, created_at)

## Step 2 — Render it

Format like this (concise — adjust if some fields are empty):

> **Signal Brain status**
>
> {raw_items} items collected · {active_claims} claims · {concepts} concepts · {pending_suggestions} drafts pending feedback
>
> **Top trends**
> 1. {name} — momentum {momentum}
> 2. ...
>
> **Recent agent activity**
> · {created_at}  {action} — {detail}
> · ...

If `pending_extraction > 0`, end with: "{pending_extraction} items waiting to be extracted on the next cycle."

If everything is zero, say: "No data yet. Run `/cycle` to do a first pass, or wait for the scheduled task to fire."

Don't dump raw JSON to the user — render it.
