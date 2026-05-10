---
description: Run one full Signal Brain cycle (ingest → heal → suggest)
---

You are running one cycle of the **Signal Brain** agent. This same prompt is used by the Cowork scheduled task. Work through the steps below using bash, do the LLM-bearing steps yourself (you ARE the LLM in this mode), and write a one-line summary at the end.

The repo root is the current working directory. The Python interpreter is `.venv/bin/python`.

## Steps

**1. Fetch new items.**
```
.venv/bin/python scripts/fetch.py
```
No LLM. Inserts raw_items. Read the output to see how many new items each source returned.

**2. Extract pending items.**
```
.venv/bin/python scripts/list_pending.py --limit 20
```
For each pending item, apply this extraction system prompt (it lives in `signal_brain/extractor.py::EXTRACTION_PROMPT`):

> You are an information-extraction component of a knowledge-brain agent. Read one piece of content (a post, article headline, comment) and extract atomic CLAIMS (factual or opinion statements that could later be verified or contradicted; each must be self-contained; stance is positive/negative/neutral) and CONCEPTS (1-5 short canonical noun phrases, lowercase, no years, no vague terms). If the item is spam, off-topic clickbait, low-signal meme, NSFW, or incoherent, set `skip: true` and return empty arrays. Prefer 1-3 sharp claims over many weak ones. Skip purely procedural content (job postings, "show HN: my project", sponsored posts). Concepts should be the kind a busy founder/sales leader would want to track over weeks. Return ONLY a JSON object: `{"skip": false, "claims": [{"text": "...", "stance": "positive|negative|neutral", "confidence": 0..1}], "concepts": ["..."]}`.

For each item, save your result:
```
.venv/bin/python scripts/save_extraction.py --raw-id N --json '<json-object>'
```
(Or pipe via `--stdin`.) Skip items where the JSON contains `"skip": true` — but still call save_extraction so the audit log records the decision.

**3. Run non-LLM healing.**
```
.venv/bin/python scripts/heal_basic.py
```
Recomputes momentum, archives stale concepts, applies user feedback to source-reliability scores. Read the JSON output.

**4. Concept-merge pass.**
```
.venv/bin/python scripts/list_concepts.py --limit 40
```
Apply this prompt:

> You are an ontology janitor. Given a list of concepts, identify groups that mean the same thing and should be merged. Examples to merge: "ai agents" + "autonomous agents" → "ai agents". DO NOT merge things that are merely related ("ai agents" vs "ai safety", "fundraising" vs "venture capital"). Return JSON: `{"merges": [{"canonical": "ai agents", "aliases": ["agentic ai"]}]}`. If nothing should merge, return `{"merges": []}`.

If you found merges:
```
.venv/bin/python scripts/save_merge.py --json '<json-object>'
```

**5. Contradiction pass.**
```
.venv/bin/python scripts/list_concepts.py --with-claims --limit 10
```
For each concept with ≥2 active claims, look for contradictions: pairs where one claim implies the other is false. Only flag clear contradictions, not differences in emphasis. For each, decide who wins by:
- higher source `reliability` first
- then more recent (claims are returned newest-first)

Save each:
```
.venv/bin/python scripts/save_supersede.py --loser <id> --winner <id> --concept "<name>" --reason "<short>"
```

**6. Draft posts.**
```
.venv/bin/python scripts/suggest_context.py
```
This returns: `{system_prompt, context: {profile, top_concepts, callback}}`. If `context.profile` is null, skip with a note "no profile set yet — user should fill it at /profile".

Otherwise, apply the system_prompt to the context to draft **3 posts**:
- Post 1: ride the strongest current trend.
- Post 2: a contrarian / sharper-take angle on a different trend.
- Post 3: a CALLBACK — connect the older `callback` concept (if present) to a current one, framed as "I noticed this weeks ago, here's what just changed". If `callback` is null, make the third post another sharp angle.

Each post:
- 250-400 chars, LinkedIn-native feel.
- Opens with a hook, ends with a question or sharp claim.
- Cites concepts via `concept_ids` and supporting sources via `source_ids` (use IDs from the context JSON).
- Don't invent statistics. If no number is available, don't make one up.

For each post, save:
```
.venv/bin/python scripts/save_suggestion.py --json '<post-object>'
```
Use shape: `{"headline":"…","body":"…","rationale":"…","concept_ids":[…],"source_ids":[…],"callback_to":null|"<concept name>"}`.

**7. Summary.**
```
.venv/bin/python scripts/status.py
```
Read the result. Write a single-line summary to the user (or to the scheduled-task log) like:
> Signal Brain cycle done — 8 new items, 14 claims added, 3 posts drafted, 1 contradiction resolved.

## On failure

If any step errors, do not panic. Note it in the summary, continue with whatever steps still make sense, and let the next scheduled run pick up the slack. The DB is idempotent — exact-hash dedup means a re-run won't double-insert.
