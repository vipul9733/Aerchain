"""
Provider-agnostic LLM client.

Supports Anthropic (Claude) and OpenAI out of the box. The agent code never
talks to a vendor SDK directly — it calls `complete()` / `complete_json()`,
so swapping providers is a single env var change.

Env vars:
    LLM_PROVIDER   = "anthropic" (default) | "openai"
    ANTHROPIC_API_KEY / OPENAI_API_KEY
    LLM_MODEL      = optional override of the default model per provider
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


class LLMError(RuntimeError):
    pass


# Runtime credentials, set by the UI when a user pastes a key. These take
# precedence over environment variables, so the app works with no terminal setup.
_RUNTIME = {"provider": None, "api_key": None, "model": None}


def set_runtime_credentials(provider: str | None = None, api_key: str | None = None,
                            model: str | None = None) -> None:
    if provider is not None:
        _RUNTIME["provider"] = provider.strip().lower() or None
    if api_key is not None:
        _RUNTIME["api_key"] = api_key.strip() or None
    if model is not None:
        _RUNTIME["model"] = model.strip() or None


def clear_runtime_credentials() -> None:
    _RUNTIME.update({"provider": None, "api_key": None, "model": None})


def has_credentials() -> bool:
    """True if a usable key is available (runtime first, then env)."""
    return bool(_resolve_key(_provider()))


def _provider() -> str:
    return (_RUNTIME["provider"] or os.getenv("LLM_PROVIDER", "anthropic")).strip().lower()


def _resolve_key(provider: str) -> str | None:
    if _RUNTIME["api_key"]:
        return _RUNTIME["api_key"]
    return os.getenv("OPENAI_API_KEY") if provider == "openai" else os.getenv("ANTHROPIC_API_KEY")


def _default_model(provider: str) -> str:
    if _RUNTIME["model"]:
        return _RUNTIME["model"]
    if provider == "openai":
        return os.getenv("LLM_MODEL", "gpt-4o")
    return os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")


def complete(
    system: str,
    user: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> str:
    """Single-turn completion. Returns raw text."""
    provider = _provider()

    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise LLMError("anthropic package not installed. `pip install anthropic`") from e
        key = _resolve_key(provider)
        if not key:
            raise LLMError("No Anthropic API key. Paste one in the sidebar or set ANTHROPIC_API_KEY.")
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=_default_model(provider),
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMError("openai package not installed. `pip install openai`") from e
        key = _resolve_key(provider)
        if not key:
            raise LLMError("No OpenAI API key. Paste one in the sidebar or set OPENAI_API_KEY.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=_default_model(provider),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    raise LLMError(f"Unknown LLM_PROVIDER: {provider!r}")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` wrappers if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _extract_first_json(text: str) -> str:
    """Best-effort: pull the first balanced {...} or [...] block out of text."""
    text = _strip_code_fences(text)
    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start is None:
        return text
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def complete_json(
    system: str,
    user: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    retries: int = 1,
) -> Any:
    """
    Completion that must return JSON. Handles the two real failure modes:

    1. TRUNCATION — the model hit the token limit and the JSON is cut off
       (unterminated string). Repairing the text can't help because data is
       genuinely missing, so we re-request the SAME prompt with a larger budget.
    2. WRAPPING/STRAY TEXT — valid JSON exists but is fenced or has preamble;
       `_extract_first_json` plus a light repair pass handles that.
    """
    raw = complete(system, user, max_tokens=max_tokens, temperature=temperature)
    candidate = _extract_first_json(raw)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as first_err:
        if retries <= 0:
            raise LLMError(
                f"Model did not return valid JSON.\nError: {first_err}\nRaw (first 2000 chars):\n{raw[:2000]}"
            ) from first_err

        # Heuristic: if the candidate has unbalanced braces, it was truncated.
        looks_truncated = candidate.count("{") > candidate.count("}") or \
            candidate.count("[") > candidate.count("]")

        if looks_truncated:
            # Re-run the original request with a much larger token budget.
            bigger = min(max(max_tokens * 2, 8192), 16000)
            raw2 = complete(system, user, max_tokens=bigger, temperature=temperature)
            try:
                return json.loads(_extract_first_json(raw2))
            except json.JSONDecodeError:
                raw = raw2  # fall through to text-repair on the bigger output

        # Last resort: ask the model to emit corrected, COMPLETE JSON.
        repair_user = (
            "The following was supposed to be a single valid, COMPLETE JSON object/array but "
            "is malformed or was cut off. Re-emit it as valid, complete JSON. Close every "
            "open string, object, and array. Output ONLY the JSON, no commentary, no fences.\n\n"
            f"{raw}"
        )
        repaired = complete(
            "You are a strict JSON repair tool. Output only valid, complete JSON.",
            repair_user,
            max_tokens=min(max(max_tokens * 2, 8192), 16000),
            temperature=0.0,
        )
        try:
            return json.loads(_extract_first_json(repaired))
        except json.JSONDecodeError as final_err:
            raise LLMError(
                "Could not obtain valid JSON after retry and repair. The response was likely "
                "truncated. Try fewer vendors at once, or a model with a larger output limit.\n"
                f"Error: {final_err}"
            ) from final_err