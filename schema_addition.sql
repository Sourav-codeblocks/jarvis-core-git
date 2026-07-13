-- Jarvis Core — Phase 0 schema ADDITION
-- Model registry: the certification gate. A model/provider pair may not serve
-- live tenant traffic until the eval engine has marked it 'green'.
--
-- This is deliberately separate from tenant_tools (which gates *tenant*
-- access to a capability). model_registry gates *system-wide* readiness of
-- a given (provider, model) pair before any tenant can reach it, regardless
-- of tier. Run this against the existing Supabase project; it only adds a
-- table, it does not touch anything already live (including `messages`,
-- which already exists there).

CREATE TABLE model_registry (
    provider        TEXT NOT NULL,               -- 'ollama_local', 'groq', 'gemini', 'openrouter', 'anthropic_api'
    model           TEXT NOT NULL,                -- 'llama-3.3-70b-versatile', 'gemini-3-flash', etc.
    task_type       TEXT NOT NULL,                -- which MODEL_MATRIX slot this is being evaluated for
    status          TEXT NOT NULL DEFAULT 'red'   -- red | yellow | green
                    CHECK (status IN ('red', 'yellow', 'green')),
    -- red    = untested or failed certification; router will never route here
    -- yellow = passed smoke test only; router may use as last-resort fallback
    -- green  = passed full eval suite; router may serve live tenant traffic
    last_run_id     TEXT,                         -- eval_runs.id of the certifying run
    last_certified_at TIMESTAMPTZ,
    notes           TEXT,                         -- human-readable summary of last result
    PRIMARY KEY (provider, model, task_type)
);

-- One row per certification run, so results are auditable over time
-- (a model can flip green -> yellow -> red as providers change silently).
CREATE TABLE eval_runs (
    id              BIGSERIAL PRIMARY KEY,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    verdict         TEXT NOT NULL CHECK (verdict IN ('red', 'yellow', 'green')),
    intent_accuracy NUMERIC(5,2),                 -- % correct on labeled intent set (if applicable)
    tool_call_ok    BOOLEAN,                      -- did it emit correctly-formatted tool calls
    refusal_ok      BOOLEAN,                      -- did it correctly refuse the safety probes
    p95_latency_ms  INT,
    error_rate      NUMERIC(5,2),                 -- % of test calls that errored/timed out
    raw_report      JSONB,                        -- full per-case results, for debugging a downgrade
    run_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX eval_runs_provider_model ON eval_runs (provider, model, run_at DESC);
