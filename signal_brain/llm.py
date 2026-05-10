"""LLM provider abstraction.

Three providers:
- 'anthropic'  — direct calls to Claude (set ANTHROPIC_API_KEY)
- 'openai'     — direct calls to OpenAI (set OPENAI_API_KEY)
- 'cowork'     — no direct API. The cycle runs *inside* a Claude Cowork session,
                 which is itself an LLM. LLM-bearing functions raise NotConfigured —
                 the Cowork session is expected to do the thinking and call the
                 atomic save scripts (`scripts/save_extraction.py`, etc.).

Selection: env var SIGNAL_BRAIN_PROVIDER=anthropic|openai|cowork. Default 'cowork'.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any

from . import config


PROVIDER = os.environ.get("SIGNAL_BRAIN_PROVIDER", "cowork").lower()


class NotConfigured(RuntimeError):
    """Raised when an LLM call is requested but no provider is configured.
    In Cowork-managed mode this is expected — the session itself is the LLM,
    and you should call the corresponding save_* script with the result."""


# ---------- Provider implementations -----------------------------------------

def _anthropic_complete(system: str, user: str, *, model: str | None = None,
                       max_tokens: int = 800, temperature: float = 0.2) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=model or config.MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))


def _openai_complete(system: str, user: str, *, model: str | None = None,
                    max_tokens: int = 800, temperature: float = 0.2) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL")  # supports OpenAI-compatible APIs
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    chosen_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=chosen_model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


# ---------- Public API --------------------------------------------------------

def complete(system: str, user: str, *, model: str | None = None,
            max_tokens: int = 800, temperature: float = 0.2) -> str:
    """Run a single completion. Raises NotConfigured in cowork mode."""
    if PROVIDER == "anthropic":
        return _anthropic_complete(system, user, model=model, max_tokens=max_tokens, temperature=temperature)
    if PROVIDER == "openai":
        return _openai_complete(system, user, model=model, max_tokens=max_tokens, temperature=temperature)
    if PROVIDER == "cowork":
        raise NotConfigured(
            "LLM call requested in Cowork-managed mode. The Cowork session is the LLM — "
            "it should do this step itself and write the result with the corresponding save_* script."
        )
    raise NotConfigured(f"Unknown SIGNAL_BRAIN_PROVIDER='{PROVIDER}'. Use 'anthropic', 'openai', or 'cowork'.")


def parse_json(raw: str) -> dict[str, Any]:
    """Tolerant JSON parser — strips code fences, recovers first object."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
