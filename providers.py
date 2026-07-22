"""Jarvis Core — provider call wrappers.

One function per provider, all normalized to the same shape so llm_router.py
and certify_model.py never need to know provider-specific request/response
formats:

    call(prompt: str, timeout: int) -> (text: str, usage: dict)
    usage = {"prompt_tokens": int, "completion_tokens": int, "cost_usd": float}

Keys come from api_key_refs (env var names), never hardcoded — same rule as
everywhere else in this codebase.
"""

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
# above on purpose. llm_router.route() and certify_model.py depend on the
# call(prompt, timeout) -> (text, usage) shape and neither needs to change.
# This exists for founder_ws.py's route_founder_query(), which needs actual
# structured tool_calls back (which tool, what arguments), not just text —
# something the flat interface has no way to carry.
#
#     raw_call(messages: list[dict], tools: list[dict] | None, timeout: int)
#         -> raw provider JSON response (shape differs per provider —
#            see founder_ws.py's _normalize_message for the adapter)
#
# Only groq and ollama_local are wired here: groq is the certified,
# working tool-calling candidate (see PROGRESS.md 2026-07-13 — confirmed
# tool-call format OK at 336ms); ollama_local is kept ready for when a
# local GPU (dslab or a new rental) is reachable again, matching the same
# "registered but not necessarily in the active chain" pattern main.py
# already uses for CLOUD_PROVIDERS.
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
            resp.raise_for_status()
            return resp.json()
    return call


_RAW_BUILDERS = {
    "ollama_local": _ollama_local_raw,
    "groq": _groq_raw,
}


def get_raw_chat_call(provider: str, model: str):
    """Returns call(messages, tools, timeout) -> raw provider JSON for
    tool-calling-capable providers only. Raises for anything not in
    _RAW_BUILDERS (e.g. gemini's function-calling schema is different
    enough that it isn't wired here yet — see founder_ws.py's chain,
    which only lists providers this function actually supports)."""
    if provider not in _RAW_BUILDERS:
        raise ValueError(f"No raw tool-calling interface for provider: {provider}")
    return _RAW_BUILDERS[provider](model)
