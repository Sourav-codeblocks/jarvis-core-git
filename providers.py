"""Jarvis Core — provider call wrappers.

One function per provider, all normalized to the same shape so llm_router.py
and certify_model.py never need to know provider-specific request/response
formats:

    call(prompt: str, timeout: int) -> (text: str, usage: dict)
    usage = {"prompt_tokens": int, "completion_tokens": int, "cost_usd": float}

Keys come from api_key_refs (env var names), never hardcoded — same rule as
everywhere else in this codebase.
"""

import json
import os
import time
import httpx

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def _ollama_local(model: str):
    def call(prompt: str, timeout: int):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "http://localhost:11434/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "cost_usd": 0.0,
        }
        return data["message"]["content"], usage
    return call


def _groq(model: str):
    # OpenAI-compatible endpoint — see console.groq.com/docs
    def call(prompt: str, timeout: int):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            data = resp.json()
        usage_raw = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "cost_usd": 0.0,  # free tier
        }
        return data["choices"][0]["message"]["content"], usage
    return call


def _gemini(model: str):
    def call(prompt: str, timeout: int):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            data = resp.json()
        usage_raw = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_raw.get("promptTokenCount"),
            "completion_tokens": usage_raw.get("candidatesTokenCount"),
            "cost_usd": 0.0,  # free tier
        }
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text, usage
    return call


def _openrouter(model: str):
    def call(prompt: str, timeout: int):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            data = resp.json()
        usage_raw = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "cost_usd": 0.0,  # ':free' suffixed models only
        }
        return data["choices"][0]["message"]["content"], usage
    return call


def _anthropic(model: str):
    def call(prompt: str, timeout: int):
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={"model": model, "max_tokens": 1024,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            resp.raise_for_status()
            data = resp.json()
        usage_raw = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("input_tokens"),
            "completion_tokens": usage_raw.get("output_tokens"),
            "cost_usd": None,  # compute from model rate card if you want $ in usage_events
        }
        text = "".join(block["text"] for block in data["content"] if block["type"] == "text")
        return text, usage
    return call


_BUILDERS = {
    "ollama_local": _ollama_local,
    "groq": _groq,
    "gemini": _gemini,
    "openrouter": _openrouter,
    "anthropic_api": _anthropic,
}


def get_provider_call(provider: str, model: str):
    """Returns call(prompt, timeout) -> (text, usage) for the given provider/model."""
    if provider not in _BUILDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return _BUILDERS[provider](model)


# ---------------------------------------------------------------------------
# Raw message/tool-calling interface — separate from the flat-prompt contract
# above on purpose. llm_router.py and certify_model.py depend on the
# call(prompt, timeout) -> (text, usage) shape and neither needs to change.
# This exists for real tool-calling callers (founder_ws.py, booking_tools.py)
# that need actual structured tool_calls back, not just text.
#
#     raw_call(messages: list[dict], tools: list[dict] | None, timeout: int)
#         -> raw provider JSON response (shape differs per provider)
#
# Added 2026-07-26: Gemini's raw tool-calling, plus normalize_tool_response()
# below — the single place that flattens every provider's differently-shaped
# response into ONE shared shape. Built after a REAL incident: Groq hit its
# free-tier daily token cap mid-testing, and the booking tool-calling layer
# had exactly one provider wired in with no fallback — every booking
# silently stopped working. This is the actual fix, not a hypothetical one.
# ---------------------------------------------------------------------------

def _ollama_local_raw(model: str):
    def call(messages: list, tools: list | None, timeout: int):
        payload = {"model": model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        url = f"{os.environ.get('OLLAMA_URL', 'http://localhost:11434')}/api/chat"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    return call


def _groq_raw(model: str):
    def call(messages: list, tools: list | None, timeout: int):
        payload = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as err:
                # Surface Groq's actual error body (rate limits, bad
                # requests, etc.) instead of swallowing it — a real gap
                # found live 2026-07-26 that cost real debugging time.
                raise httpx.HTTPStatusError(
                    f"{err} — body: {resp.text}", request=err.request, response=err.response
                ) from None
            return resp.json()
    return call


def _gemini_raw(model: str):
    """Gemini's function-calling API has a genuinely different shape than
    Groq/OpenAI's — this is the translation layer. Converts OpenAI-style
    `messages` (system/user/assistant) into Gemini's `contents` +
    `systemInstruction`, and OpenAI-style `tools` into Gemini's
    `function_declarations`. The raw response this returns still needs
    normalize_tool_response() to become the shared shape every caller
    actually uses."""
    def call(messages: list, tools: list | None, timeout: int):
        system_text_parts = []
        contents = []
        for m in messages:
            if m["role"] == "system":
                system_text_parts.append(m["content"])
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": m["content"]}]})
            else:  # user
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})

        payload: dict = {"contents": contents}
        if system_text_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n".join(system_text_parts)}]}
        if tools:
            function_declarations = []
            for t in tools:
                fn = t["function"]
                function_declarations.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = [{"function_declarations": function_declarations}]

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as err:
                raise httpx.HTTPStatusError(
                    f"{err} — body: {resp.text}", request=err.request, response=err.response
                ) from None
            return resp.json()
    return call


def _openrouter_raw(model: str):
    """OpenRouter's chat completions endpoint is OpenAI-compatible, same
    shape as Groq's — no translation layer needed, unlike Gemini."""
    def call(messages: list, tools: list | None, timeout: int):
        payload = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as err:
                raise httpx.HTTPStatusError(
                    f"{err} — body: {resp.text}", request=err.request, response=err.response
                ) from None
            return resp.json()
    return call


_RAW_BUILDERS = {
    "ollama_local": _ollama_local_raw,
    "groq": _groq_raw,
    "gemini": _gemini_raw,
    "openrouter": _openrouter_raw,
}


def get_raw_chat_call(provider: str, model: str):
    """Returns call(messages, tools, timeout) -> raw provider JSON for
    tool-calling-capable providers. Raises for anything not in
    _RAW_BUILDERS."""
    if provider not in _RAW_BUILDERS:
        raise ValueError(f"No raw tool-calling interface for provider: {provider}")
    return _RAW_BUILDERS[provider](model)


def normalize_tool_response(provider: str, raw: dict) -> dict:
    """THE single place every provider's differently-shaped tool-calling
    response gets flattened into ONE shared shape:

        {"content": str | None, "tool_calls": [{"function": {"name": str, "arguments": json_str}}]}

    Before this, founder_ws.py had its OWN inline normalizer and
    booking_tools.py just assumed Groq's raw shape directly with no
    normalization at all — two different, inconsistent patterns for the
    same problem. This is the one shared version both should use."""
    if provider in ("groq", "ollama_local", "openrouter"):
        msg = raw.get("message", {}) if provider == "ollama_local" else raw["choices"][0]["message"]
        return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls") or []}

    if provider == "gemini":
        try:
            parts = raw["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            return {"content": None, "tool_calls": []}
        tool_calls, text_parts = [], []
        for p in parts:
            if "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append({
                    "function": {"name": fc["name"], "arguments": json.dumps(fc.get("args", {}))},
                })
            elif "text" in p:
                text_parts.append(p["text"])
        return {"content": "\n".join(text_parts) or None, "tool_calls": tool_calls}

    raise ValueError(f"normalize_tool_response: unknown provider {provider!r}")
