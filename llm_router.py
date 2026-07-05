"""LLM routing — the 'right model for the right job' matrix + provider fallback.

Lessons already proven in your own labs:
- llama3.1:8b failed multi-step tool calling; qwen2.5:7b-instruct succeeded.
  => tool-calling agent turns go to qwen-class models.
- Tiny models are fine for classification and near-free.
- Fallback chain makes 'own GPUs someday' a config change, not a rewrite.

Research routing: the router decides retrieval strategy per query —
  fresh/current-events => web_search tool; tenant knowledge => RAG tool.
That is a flag on the task, not a separate architecture.
"""

import time

# task_type -> ordered list of (provider, model). First healthy wins.
MODEL_MATRIX = {
    # High volume, must be near-free:
    "intent":     [("ollama_local", "llama3.2:3b-instruct-q8_0")],
    # Tool-calling agent turns (proven need for qwen-class):
    "agent_turn": [("ollama_local", "qwen2.5:7b-instruct-q8_0"),
                   ("anthropic_api", "claude-haiku-4-5-20251001")],
    # Longer prose / drafting:
    "draft":      [("ollama_local", "mistral:7b-instruct-q8_0"),
                   ("anthropic_api", "claude-sonnet-4-6")],
    # Hard reasoning, premium tier escalation only:
    "escalation": [("anthropic_api", "claude-sonnet-4-6")],
}

# Premium tenants may escalate; basic tenants stay local-only.
TIER_ALLOWS_CLOUD = {"basic": False, "pro": True, "premium": True}

PROVIDER_TIMEOUT_S = {"ollama_local": 60, "anthropic_api": 45}


class AllProvidersFailed(Exception):
    pass


def route(task_type: str, prompt: str, tenant_tier: str, providers, usage_logger):
    """providers: dict provider_name -> callable(model, prompt, timeout) -> (text, usage)
    usage_logger: callable writing one usage_events row per call."""
    chain = MODEL_MATRIX[task_type]
    last_err = None

    for provider_name, model in chain:
        if provider_name != "ollama_local" and not TIER_ALLOWS_CLOUD[tenant_tier]:
            continue  # basic tier never leaves local

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

    raise AllProvidersFailed(f"{task_type}: all providers failed; last: {last_err}")
