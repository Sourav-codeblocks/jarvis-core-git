-- Jarvis Core — Eval Engine schema addition (Postgres / Supabase compatible)
-- Follows the same conventions as schema.sql: tenant scoping, TIMESTAMPTZ,
-- BIGSERIAL PKs. This is telemetry for MODEL CANDIDATES, kept separate from
-- usage_events (which is production traffic telemetry).

CREATE TABLE llm_evaluations (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              UUID NOT NULL,               -- groups all cases from one eval sweep
    tenant_slug         TEXT NOT NULL REFERENCES tenants(slug),

    test_label          TEXT NOT NULL,                -- 'happy_inventory_query'
    test_category       TEXT NOT NULL                 -- happy_path | boundary | adversarial |
                        CHECK (test_category IN (      -- out_of_distribution | regression
                            'happy_path', 'boundary', 'adversarial',
                            'out_of_distribution', 'regression'
                        )),
    input_text          TEXT NOT NULL,

    candidate_provider  TEXT NOT NULL,                 -- 'runpod_gpu'
    candidate_model     TEXT NOT NULL,                 -- 'llama3:8b-instruct-q4_K_M'

    raw_output          TEXT,
    generation_error    TEXT,                          -- non-null = hard fail, tier2 was skipped
    latency_ms          INT,

    tier1_result        JSONB NOT NULL DEFAULT '{}',   -- {passed, kw_missing, forbidden_found, ...}
    tier2_result         JSONB NOT NULL DEFAULT '{}',   -- {correctness..tone, craft_total, judge_provider, judge_model, reasoning}

    passed               BOOLEAN NOT NULL,

    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_llm_evaluations_run ON llm_evaluations (run_id);
CREATE INDEX idx_llm_evaluations_candidate ON llm_evaluations (tenant_slug, candidate_provider, candidate_model, created_at);
CREATE INDEX idx_llm_evaluations_category ON llm_evaluations (test_category, passed);

-- One row per (candidate model, run) summary, refreshed by the readiness
-- endpoint's aggregate query rather than a materialized view for now —
-- Phase 0.5, revisit once eval volume justifies a view.
