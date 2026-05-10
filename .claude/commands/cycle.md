---
description: Run one full Signal Brain cycle (fetch → extract → heal → suggest)
---

You are running one cycle of the **Signal Brain** agent. This same prompt is the body of the Cowork scheduled task. You ARE the LLM in this mode — do the thinking yourself between bash calls.

The repo root is the current working directory. Use `python3` (not `.venv/bin/python`) — Cowork mode doesn't need the host venv.

**Important:** in Cowork mode the sandbox's outbound proxy 403s most public APIs. Fetch via the **WebFetch tool**, not `scripts/fetch.py`. WebFetch has a much wider allowlist and is the right tool for this job — using it makes the Cowork session itself the agent's network layer, which is the point of Cowork mode.

## Steps

**1. Discover sources.**
```
python3 scripts/list_sources.py
```
Returns a JSON array. Each entry: `{id, kind, handle, label, fetch_url, format}`. The `fetch_url` is the URL you should pull; `format` is `rss` (RSS/Atom feed) or `json` (raw JSON).

**2. Fetch each source via WebFetch.**

For every enabled source, call `WebFetch` with the source's `fetch_url` and a prompt that asks for up to 25 recent items as JSON. Use roughly:

> Extract up to 25 of the most recent items from this feed/page as a JSON array. Each item must have: `external_id` (a stable per-feed id — the GUID, link URL, or post ID), `title`, `url` (the canonical link to the item), `body` (a short summary or first paragraph), `posted_at` (ISO 8601), and `score` (an integer like upvotes/likes if visible, else 0). Return ONLY the JSON array, no prose.

Then, for each item the WebFetch returned, call:
```
python3 scripts/save_raw_item.py --source-id <id> --json '<item-json>'
```
The script hash-dedups, so re-running across cycles is safe. If it returns `{"skipped": true}` that's expected.

If a source's WebFetch fails (timeout, 403, etc.), log it and move on — the next cycle will retry.

**3. Extract pending items.**
```
python3 scripts/list_pending.py --limit 20
```
For each pending item, apply the EXTRACTION_PROMPT below:

> You are an information-extraction component of a knowledge-brain agent. Read one piece of content (a post, article headline, comment) and extract atomic CLAIMS (factual or opinion statements that could later be verified or contradicted; each must be self-contained; stance is positive/negative/neutral) and CONCEPTS (1-5 short canonical noun phrases, lowercase, no years, no vague terms). If the item is spam, off-topic clickbait, low-signal meme, NSFW, or incoherent, set `skip: true` and return empty arrays. Prefer 1-3 sharp claims over many weak ones. Skip purely procedural content (job postings, "show HN: my project", sponsored posts). Concepts should be the kind a busy founder/sales leader would want to track over weeks. Return ONLY a JSON object: `{"skip": false, "claims": [{"text": "...", "stance": "positive|negative|neutral", "confidence": 0..1}], "concepts": ["..."]}`.

Save each result:
```
python3 scripts/save_extraction.py --raw-id N --json '<json-object>'
```

**4. Run non-LLM healing.**
```
python3 scripts/heal_basic.py
```
Recomputes momentum, archives stale concepts, applies feedback to source-reliability scores.

**5. Concept-merge pass.**
```
python3 scripts/list_concepts.py --limit 40
```
Apply this prompt:

> You are an ontology janitor. Given a list of concepts, identify groups that mean the same thing and should be merged. Examples to merge: "ai agents" + "autonomous agents" → "ai agents". DO NOT merge things that are merely related ("ai agents" vs "ai safety"). Return JSON: `{"merges": [{"canonical": "ai agents", "aliases": ["agentic ai"]}]}`. If nothing should merge, return `{"merges": []}`.

If you found merges:
```
python3 scripts/save_merge.py --json '<json-object>'
```

**6. Contradiction pass.**
```
python3 scripts/list_concepts.py --with-claims --limit 10
```
For each concept with ≥2 active claims, look for contradictions. Only flag clear ones. Decide who wins by: higher `reliability` first, then more recent.

```
python3 scripts/save_supersede.py --loser <id> --winner <id> --concept "<name>" --reason "<short>"
```

**7. Draft posts.**
```
python3 scripts/suggest_context.py
```
Returns `{system_prompt, context: {profile, top_concepts, callback}}`. If `profile` is null, skip with a one-line note.

Otherwise apply the system_prompt and draft **3 posts**: ride-the-trend, contrarian, and a callback (use the `callback` concept if present, else another sharp angle). Each post 250-400 chars, opens with a hook, ends with a question. Cite concept_ids and source_ids from the context. Don't invent statistics.

```
python3 scripts/save_suggestion.py --json '<post-object>'
```
Shape: `{"headline":"…","body":"…","rationale":"…","concept_ids":[…],"source_ids":[…],"callback_to":null|"<concept name>"}`.

**8. Summary.**
```
python3 scripts/status.py
```
Write a one-line summary. Example:
> Signal Brain cycle done — 12 new items, 18 claims added, 3 posts drafted, 1 contradiction resolved.

## On failure

If a step errors, note it briefly and continue. The DB is idempotent (content-hash dedup). Next scheduled run picks up the slack.
