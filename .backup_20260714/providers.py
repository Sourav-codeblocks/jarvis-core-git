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
