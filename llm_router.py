"""LLM routing — the 'right model for the right job' matrix + provider fallback.

Lessons already proven in your own labs:
- llama3.1:8b failed multi-step tool calling; qwen2.5:7b-instruct succeeded.
  => tool-calling agent turns go to qwen-class models.
- Tiny models are fine for classification and near-free.
- Fallback chain makes 'own GPUs someday' a config change, not a rewrite.

2026-07 update: dslab GPU/Ollama is not always reachable, so every task_type
now has a free-tier cloud fallback chain behind local:

    ollama_local -> gemini -> groq -> openrouter -> anthropic_api (paid, escalation only)

Ordering rationale (see PROGRESS.md for the numbers): Gemini Flash/Flash-Lite
survives real traffic volume (1,500 req/day, ~1M tokens/min) far better than
Groq (~1,000 req/day, 6-12K tokens/min per model), so it sits first as the
'doesn't get exhausted' choice. Groq is faster per-call and sits second as
the speed fallback. OpenRouter's free pool is the last-resort net because it
draws from many underlying providers with independent quotas.

CERTIFICATION GATE: no (provider, model, task_type) triple may serve live
tenant traffic unless model_registry marks it 'green' (see certify_model.py).
A brand-new provider added here does nothing until someone runs certify_model.py
against it — the router will silently skip anything not certified, exactly
like a disabled row in tenant_tools skips a tool.

Research routing: the router decides retrieval strategy per query —
  fresh/current-events => web_search tool; tenant knowledge => RAG tool.
That is a flag on the task, not a separate architecture.
"""

import time

from db_client import get_supabase

# task_type -> ordered list of (provider, model). First CERTIFIED-and-healthy wins.
MODEL_MATRIX = {
    # High volume, must be near-free:
    "intent": [
        ("ollama_local", "llama3.2:3b-instruct-q8_0"),
        ("gemini", "gemini-flash-lite-latest"),
        ("groq", "llama-3.1-8b-instant"),
    ],
    # TEMP (2026-07-13, demo week): RunPod terminated, dslab GPU not
    # reliable -- agent_turn runs on Groq/Gemini free tier ONLY until a
    # rented GPU cluster is up. ollama_local/openrouter/anthropic_api
    # removed from THIS chain only (not touched elsewhere) so the router
    # doesn't waste a timeout on a dead local endpoint or reach for a paid
    # provider by accident. Put ollama_local back at the front once local
    # inference is reliable again -- ordering elsewhere is untouched.
    "agent_turn": [
        ("groq", "llama-3.3-70b-versatile"),   # CERTIFIED GREEN (PROGRESS.md 2026-07-13)
        ("gemini", "gemini-flash-latest"),     # currently RED/contested -- re-certify after quota reset; harmless to leave here, router skips non-green/yellow automatically
    ],
    # Longer prose / drafting:
    "draft": [
        ("ollama_local", "mistral:7b-instruct-q8_0"),
        ("gemini", "gemini-flash-latest"),
        ("groq", "llama-3.3-70b-versatile"),
        ("anthropic_api", "claude-sonnet-4-6"),
    ],
    # Hard reasoning, premium tier escalation only:
    "escalation": [("anthropic_api", "claude-sonnet-4-6")],
}

# TEMP (2026-07-13, demo week): basic tenants normally stay local-only, but
# local (RunPod/dslab) is down and Groq/Gemini are free tier right now, so
# basic is allowed cloud too. Revert to False once local is reliable again
# and cost-bearing cloud needs the real pro/premium gate back.
TIER_ALLOWS_CLOUD = {"basic": True, "pro": True, "premium": True}

PROVIDER_TIMEOUT_S = {
    "ollama_local": 60,
    "gemini": 30,
    "groq": 20,
    "openrouter": 30,
    "anthropic_api": 45,
}


class AllProvidersFailed(Exception):
    pass


def _certified_status(provider: str, model: str, task_type: str) -> str | None:
    """Reads model_registry. Returns 'green' | 'yellow' | 'red' | None (never certified)."""
    supabase = get_supabase()
    result = (
        supabase.table("model_registry")
        .select("status")
        .eq("provider", provider).eq("model", model).eq("task_type", task_type)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]["status"]


def route(task_type: str, prompt: str, tenant_tier: str, providers, usage_logger,
          allow_yellow_fallback: bool = True):
    """providers: dict provider_name -> callable(model, prompt, timeout) -> (text, usage)
    usage_logger: callable writing one usage_events row per call.

    Two passes: first try every GREEN candidate in chain order. Only if every
    green candidate fails (or none exist) do we fall back to YELLOW candidates
    — better a degraded reply than a hard failure, but this should be rare and
    alerts on it are worth adding once this is live.
    """
    chain = MODEL_MATRIX[task_type]
    last_err = None

    for min_status in (["green"] if not allow_yellow_fallback else ["green", "yellow"]):
        for provider_name, model in chain:
            if provider_name != "ollama_local" and not TIER_ALLOWS_CLOUD[tenant_tier]:
                continue  # basic tier never leaves local

            status = _certified_status(provider_name, model, task_type)
            if status != min_status:
                continue  # only act on candidates matching this pass's tier

            call = providers[provider_name]
            started = time.monotonic()
            try:
                text, usage = call(model=model, prompt=prompt,
                                   timeout=PROVIDER_TIMEOUT_S[provider_name])
                usage_logger(task_type=task_type, model=model, provider=provider_name,
                             latency_ms=int((time.monotonic() - started) * 1000),
                             **usage)
                return text
            except Exception as err:  # timeout, connection, provider error -> next in chain
                last_err = err
                continue

    raise AllProvidersFailed(
        f"{task_type}: all certified providers failed or none certified; last: {last_err}"
    )
