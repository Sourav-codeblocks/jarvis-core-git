"""LLM routing — the 'right model for the right job' matrix + provider fallback.

Phase 0 lessons already proven in your own labs:
- llama3.1:8b failed multi-step tool calling; qwen2.5:7b-instruct succeeded.
  => tool-calling agent turns go to qwen-class models.
- Tiny models are fine for classification and near-free.
- Fallback chain makes 'own GPUs someday' a config change, not a rewrite.

Phase 0.5 addition (eval engine):
- RunPod hosts candidate models under evaluation (vLLM/Ollama, OpenAI-compatible
  API). These are NOT in MODEL_MATRIX yet — that's the point. call_direct() lets
  the eval engine hit an arbitrary (provider, model) pair that hasn't been
  promoted to production routing. Once a candidate clears the eval gate, IT gets
  added to MODEL_MATRIX as a normal entry — same mechanism, no special case.
- Judge calls are a SEPARATE chain (JUDGE_MATRIX) from production task routing,
  deliberately never pointed at the same provider as the candidate under test.
  Which judge (Anthropic vs Gemini) is a research question you're still running —
  swap JUDGE_MATRIX's default order, nothing else changes.
"""

import os
import time
import httpx

# ─────────────────────────────────────────────────────────────────
# PRODUCTION routing (unchanged from Phase 0, one bug fixed below)
# ─────────────────────────────────────────────────────────────────

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

PROVIDER_TIMEOUT_S = {
    "ollama_local": 60,
    "anthropic_api": 45,
    "gemini_api": 45,
    "groq_api": 30,         # Groq is built for speed, keep this tight
    "together_api": 45,
    "nim_api": 45,
    "runpod_gpu": 90,       # cold-start on a spun-up pod can be slow; give it room
}


class AllProvidersFailed(Exception):
    pass


def route(task_type: str, prompt: str, tenant_tier: str, providers, usage_logger,
          system: str | None = None):
    """providers: dict provider_name -> callable(model, prompt, timeout, system=None) -> (text, usage)
    usage_logger: callable writing one usage_events row per call."""
    chain = MODEL_MATRIX[task_type]
    last_err = None

    for provider_name, model in chain:
        if provider_name != "ollama_local" and not TIER_ALLOWS_CLOUD[tenant_tier]:
            continue  # basic tier never leaves local

        # FIX (code_review.md #2): providers.get() instead of providers[...] —
        # a provider missing from the caller's dict (e.g. anthropic_api not
        # configured on this box) now falls through to the next chain entry
        # instead of throwing an uncaught KeyError and crashing the router.
        call = providers.get(provider_name)
        if call is None:
            last_err = KeyError(f"provider '{provider_name}' not configured")
            continue

        started = time.monotonic()
        try:
            text, usage = call(model=model, prompt=prompt, system=system,
                               timeout=PROVIDER_TIMEOUT_S[provider_name])
            usage_logger(task_type=task_type, model=model, provider=provider_name,
                         latency_ms=int((time.monotonic() - started) * 1000),
                         **usage)
            return text
        except Exception as err:  # timeout, connection, provider error -> next in chain
            last_err = err
            continue

    raise AllProvidersFailed(f"{task_type}: all providers failed; last: {last_err}")


# ─────────────────────────────────────────────────────────────────
# EVAL-ENGINE routing (new)
# ─────────────────────────────────────────────────────────────────

def call_direct(provider_name: str, model: str, prompt: str, providers: dict,
                 timeout: float | None = None, system: str | None = None):
    """Call one specific (provider, model) directly, no MODEL_MATRIX lookup,
    no tier gating, no fallback chain.

    This is what the eval engine uses to hit a candidate model that isn't
    promoted to production routing yet — that's the entire reason it's on
    RunPod and not baked into MODEL_MATRIX. Returns (text, usage).

    system: the production system prompt (persona + RAG context), if any.
    Passed as a real system-role message where the provider supports it —
    NOT concatenated into prompt — so eval reproduces what main.py's
    ask_llm() actually sends, not an approximation of it.
    """
    call = providers.get(provider_name)
    if call is None:
        raise AllProvidersFailed(f"provider '{provider_name}' not configured")
    t = timeout or PROVIDER_TIMEOUT_S.get(provider_name, 60)
    return call(model=model, prompt=prompt, timeout=t, system=system)


# Judge routing is intentionally separate from MODEL_MATRIX: production task
# routing and "who grades the homework" must never accidentally share a chain.
# Default order is a live research question (see PROGRESS.md backlog) — swap
# the order here, nothing downstream needs to change.
JUDGE_MATRIX = [
    ("gemini_api", "gemini-flash-latest"),   # confirmed working 2026-07-12
    ("groq_api", "llama-3.3-70b-versatile"),  # confirmed working 2026-07-12; confirm current id at console.groq.com/docs/models — Groq deprecates fast
    ("together_api", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),  # NOT YET TESTED as a judge — confirm exact model string at api.together.ai/models before trusting scores from this
    ("nim_api", "meta/llama-3.1-70b-instruct"),  # NOT YET TESTED — confirm exact model string at build.nvidia.com/models before trusting scores; NIM naming is org-prefixed and changes, don't assume this is current
    ("anthropic_api", "claude-haiku-4-5-20251001"),  # key present but invalid as of 2026-07-13, needs regeneration
]


def call_judge(prompt: str, providers: dict, exclude_provider: str | None = None,
                only_provider: str | None = None):
    """Run the judge chain. exclude_provider guards against a candidate model
    and the judge accidentally landing on the same provider (self-grading) —
    pass the candidate's provider_name in and this chain skips it.

    only_provider: for debugging — force ONE specific judge provider instead
    of the fallback chain, so you can tell which judge actually works instead
    of silently falling through to a failure."""
    chain = [(p, m) for p, m in JUDGE_MATRIX if p == only_provider] if only_provider else JUDGE_MATRIX
    last_err = None
    for provider_name, model in chain:
        if provider_name == exclude_provider:
            continue
        call = providers.get(provider_name)
        if call is None:
            last_err = KeyError(f"judge provider '{provider_name}' not configured")
            continue
        try:
            return call_direct(provider_name, model, prompt, providers), provider_name, model
        except Exception as err:
            last_err = err
            continue
    raise AllProvidersFailed(f"judge: all judge providers failed; last: {last_err}")


# ─────────────────────────────────────────────────────────────────
# Provider callables
# ─────────────────────────────────────────────────────────────────
# Each returns (text: str, usage: dict) where usage has keys matching
# usage_events columns: prompt_tokens, completion_tokens, cost_usd.
# All are OpenAI-chat-compatible or provider-native; adjust base URLs via env.

def make_runpod_provider(base_url: str | None = None):
    """RunPod GPU box serving candidate models under evaluation.
    vLLM and recent Ollama builds both expose an OpenAI-compatible
    /v1/chat/completions endpoint, so one client covers both."""
    url = (base_url or os.environ.get("RUNPOD_ENDPOINT_URL", "")).rstrip("/")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        if not url:
            raise RuntimeError("RUNPOD_ENDPOINT_URL not set")
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = httpx.post(
            f"{url}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.0,
                "stream": False,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": 0,  # you're paying for the pod by the hour, not per token
        }
    return call


def make_anthropic_provider(api_key: str | None = None):
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        # Rough Haiku pricing; update if you pin a different model.
        cost = usage.get("input_tokens", 0) * 1e-6 + usage.get("output_tokens", 0) * 5e-6
        return text, {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
            "cost_usd": round(cost, 6),
        }
    return call


def make_gemini_provider(api_key: str | None = None):
    key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"X-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return text, {
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "cost_usd": 0,  # fill in once you're tracking Gemini billing tier
        }
    return call


def make_dslab_provider(base_url: str | None = None):
    """DS lab GPU, reached via the SSH tunnel from COMMANDS.md
    (`ssh -L 11434:localhost:11434 teaching@172.18.40.103`). Uses Ollama's
    NATIVE /api/chat — this is the exact call main.py already makes in
    production, kept identical here on purpose so eval results are
    comparable to what production actually does."""
    url = (base_url or os.environ.get("OLLAMA_DSLAB_URL", "http://localhost:11434")).rstrip("/")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = httpx.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"], {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "cost_usd": 0,
        }
    return call


def make_groq_provider(api_key: str | None = None):
    """Groq's free tier — fast inference, OpenAI-compatible API. Model IDs
    change often as Groq deprecates old ones; check
    console.groq.com/docs/models before relying on the default here."""
    key = api_key or os.environ.get("GROQ_API_KEY", "")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.0,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": 0,  # free tier
        }
    return call


def make_together_provider(api_key: str | None = None):
    """Together.ai — serverless inference for open-weight models (Llama,
    Qwen, Mistral, etc.), OpenAI-compatible API. No GPU to manage, no
    availability risk — this is the fix for RunPod's Community Cloud
    reclaim problem: don't rent hardware, call an endpoint someone else
    keeps running. Model catalog: https://api.together.ai/models"""
    key = api_key or os.environ.get("TOGETHER_API_KEY", "")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = httpx.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.0,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": 0,  # fill in once you're tracking Together's per-token billing
        }
    return call


def make_nim_provider(base_url: str | None = None, api_key: str | None = None):
    """NVIDIA NIM (build.nvidia.com) — hosted inference for NVIDIA-optimized
    open models. OpenAI-compatible API, same shape as Together/Groq/RunPod.
    Needs an API key from build.nvidia.com (their catalog calls it an
    'API key', generated per-model or account-wide depending on their
    current UI — check there, don't assume)."""
    url = (base_url or "https://integrate.api.nvidia.com").rstrip("/")
    key = api_key or os.environ.get("NVIDIA_API_KEY", "")

    def call(model: str, prompt: str, timeout: float, system: str | None = None):
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        resp = httpx.post(
            f"{url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.0,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return text, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "cost_usd": 0,
        }
    return call


def default_providers() -> dict:
    """Wire up the standard provider set from env vars. Call once at
    orchestrator startup; pass the resulting dict into route()/call_direct().

    ollama_local (dslab) requires the SSH tunnel from COMMANDS.md to be open
    on whatever box runs this — it will not resolve on its own."""
    return {
        "runpod_gpu": make_runpod_provider(),
        "together_api": make_together_provider(),
        "nim_api": make_nim_provider(),
        "ollama_local": make_dslab_provider(),
        "anthropic_api": make_anthropic_provider(),
        "gemini_api": make_gemini_provider(),
        "groq_api": make_groq_provider(),
    }
