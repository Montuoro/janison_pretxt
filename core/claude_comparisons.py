"""LLM paired comparison calls — supports Anthropic, OpenAI, Gemini, Groq."""

import json

SYSTEM_PROMPT = """You are an expert psychometrician assessing item difficulty for a standardised test.
You will be shown two test items. Determine which item is MORE DIFFICULT for the target student population.
Consider cognitive complexity, number of steps, mathematical concepts required, and potential for errors.

Respond ONLY with valid JSON (no markdown fences):
{"harder": "A" or "B", "confidence": 1-5, "reasoning": "brief explanation"}
"""

# ── Provider registry ────────────────────────────────────────────────────────

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "placeholder": "sk-ant-...",
        "models": [
            {"label": "Claude Sonnet 4", "value": "claude-sonnet-4-20250514"},
            {"label": "Claude Haiku 3.5", "value": "claude-haiku-4-5-20251001"},
        ],
        "default": "claude-sonnet-4-20250514",
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "placeholder": "sk-...",
        "models": [
            {"label": "GPT-4o mini (cheap)", "value": "gpt-4o-mini"},
            {"label": "GPT-4o", "value": "gpt-4o"},
            {"label": "GPT-4.1 nano (cheapest)", "value": "gpt-4.1-nano"},
        ],
        "default": "gpt-4o-mini",
    },
    "gemini": {
        "label": "Google Gemini (free tier)",
        "placeholder": "AIza...",
        "models": [
            {"label": "Gemini 2.0 Flash (free)", "value": "gemini-2.0-flash"},
            {"label": "Gemini 2.0 Flash Lite (free)", "value": "gemini-2.0-flash-lite"},
            {"label": "Gemini 1.5 Flash", "value": "gemini-1.5-flash"},
        ],
        "default": "gemini-2.0-flash",
    },
    "groq": {
        "label": "Groq (free tier)",
        "placeholder": "gsk_...",
        "models": [
            {"label": "Llama 3.3 70B", "value": "llama-3.3-70b-versatile"},
            {"label": "Llama 3.1 8B (fastest)", "value": "llama-3.1-8b-instant"},
            {"label": "Qwen3 32B", "value": "qwen/qwen3-32b"},
        ],
        "default": "llama-3.3-70b-versatile",
    },
}


def _format_item(item: dict, label: str) -> str:
    parts = [f"**Item {label}** (ID: {item['item_id']})"]
    parts.append(f"Stem: {item['stem']}")
    for opt_key in ["option_a", "option_b", "option_c", "option_d"]:
        val = item.get(opt_key, "")
        if val and str(val).strip():
            parts.append(f"  {opt_key[-1].upper()}) {val}")
    parts.append(f"Correct answer: {item.get('correct_answer', 'N/A')}")
    try:
        if int(item.get("max_score", 1)) > 1:
            parts.append(f"Max score: {item['max_score']}")
    except (ValueError, TypeError):
        pass
    return "\n".join(parts)


def _parse_response(text: str) -> dict:
    """Extract JSON from an LLM response, stripping markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"harder": "A", "confidence": 1, "reasoning": f"Parse error: {text[:100]}"}


# ── Provider-specific callers ────────────────────────────────────────────────

def _call_anthropic(api_key: str, model: str, system: str, user_msg: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=300, system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text


def _call_openai(api_key: str, model: str, system: str, user_msg: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model, max_tokens=300,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    return resp.choices[0].message.content


def _call_gemini(api_key: str, model: str, system: str, user_msg: str) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=user_msg,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=300,
        ),
    )
    return resp.text


def _call_groq(api_key: str, model: str, system: str, user_msg: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model, max_tokens=300,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    return resp.choices[0].message.content


_CALLERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "gemini": _call_gemini,
    "groq": _call_groq,
}


# ── Public API ───────────────────────────────────────────────────────────────

def create_client(provider: str, api_key: str):
    """Validate that we can reach the provider (light check)."""
    if provider not in _CALLERS:
        raise ValueError(f"Unknown provider: {provider}")
    if not api_key:
        raise ValueError("API key is required.")
    return True  # actual client created per-call for simplicity


def _parse_retry_delay(err_str: str, attempt: int) -> float:
    """Extract wait time from rate-limit error messages.

    Handles formats like:
      'Please try again in 2m45.024s'
      'Please try again in 45s'
      'retry_after: 30'
    Falls back to exponential backoff if parsing fails.
    """
    import re

    # Try "Xm Y.Zs" format (e.g., "2m45.024s")
    match = re.search(r"(\d+)m([\d.]+)s", err_str)
    if match:
        return float(match.group(1)) * 60 + float(match.group(2)) + 1

    # Try plain seconds "X.Ys" or "Xs" (e.g., "45.024s", "30s")
    match = re.search(r"(?:in|after)\s*([\d.]+)\s*s", err_str, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1

    # Fallback: exponential backoff (5s, 10s, 20s, 40s, ...)
    return min(5 * (2 ** attempt), 120)


def compare_pair(provider: str, api_key: str, item_a: dict, item_b: dict,
                 model: str = None, extra_rules: str = "",
                 max_retries: int = 5) -> dict:
    """Ask an LLM which item is harder, with retry on rate limits.

    Args:
        provider: one of 'anthropic', 'openai', 'gemini', 'groq'.
        api_key: API key for the provider.
        item_a, item_b: item dicts with 'item_id', 'stem', etc.
        model: model ID (defaults to provider's default).
        extra_rules: additional context to inject.
        max_retries: number of retries on rate-limit / transient errors.

    Returns:
        dict with keys: harder ('A' or 'B'), confidence (int), reasoning (str).
    """
    import time as _time

    if model is None:
        model = PROVIDERS[provider]["default"]

    user_msg = _format_item(item_a, "A") + "\n\n" + _format_item(item_b, "B")

    system = SYSTEM_PROMPT
    if extra_rules:
        system += f"\n\nAdditional rules from the user:\n{extra_rules}"

    caller = _CALLERS[provider]

    for attempt in range(max_retries + 1):
        try:
            text = caller(api_key, model, system, user_msg)
            return _parse_response(text)
        except Exception as e:
            err_str = str(e)
            is_rate_limit = any(k in err_str for k in ["429", "rate", "quota", "RESOURCE_EXHAUSTED"])

            # Zero-quota errors (limit: 0) — don't retry, fail fast
            if "limit: 0" in err_str:
                raise RuntimeError(
                    f"Your {PROVIDERS[provider]['label']} account has zero API quota. "
                    f"Enable billing or try a different provider (Groq has a reliable free tier)."
                ) from e

            if is_rate_limit and attempt < max_retries:
                wait = _parse_retry_delay(err_str, attempt)
                _time.sleep(wait)
                continue

            raise
