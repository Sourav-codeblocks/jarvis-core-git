-- Jarvis Core — Model Catalog (Phase 0.5, part 2)
-- Separate from llm_evaluations on purpose: this table is INVENTORY (what
-- models exist, where, and whether we've wired them up), not RESULTS (how
-- they scored). A model can sit here for weeks with status='catalogued'
-- before anyone runs a single eval case against it.

CREATE TABLE model_catalog (
    id            BIGSERIAL PRIMARY KEY,

    source        TEXT NOT NULL                       -- where the model lives
                  CHECK (source IN (
                      'dslab', 'runpod', 'nvidia_nim',
                      'anthropic_api', 'gemini_api', 'groq_api', 'other'
                  )),
    provider_key  TEXT,                                -- matches llm_router.py's providers
                                                        -- dict key once wired, e.g. 'ollama_local'.
                                                        -- NULL until someone actually adds the
                                                        -- provider callable.
    model_name    TEXT NOT NULL,                        -- 'llama3.2:3b-instruct-q8_0',
                                                        -- 'meta/llama-3.1-405b-instruct' (NIM), etc.

    role          TEXT NOT NULL DEFAULT 'candidate'
                  CHECK (role IN ('candidate', 'judge_candidate', 'production')),

    status        TEXT NOT NULL DEFAULT 'catalogued'
                  CHECK (status IN (
                      'catalogued',   -- we know it exists, nothing wired
                      'wired',        -- provider callable exists in llm_router.py
                      'testing',      -- eval runs happening against it
                      'evaluated',    -- has at least one llm_evaluations run to reference
                      'promoted',     -- live in MODEL_MATRIX or JUDGE_MATRIX
                      'deprecated'    -- retired, keep the row for history
                  )),

    notes         TEXT,                                 -- free text: pricing, rate limits,
                                                        -- context window, why it's here
    added_at      TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),

    UNIQUE (source, model_name)
);

CREATE INDEX idx_model_catalog_status ON model_catalog (status);
CREATE INDEX idx_model_catalog_role ON model_catalog (role);

-- Seed: what's actually wired and running as of 2026-07-12. Everything else
-- (NVIDIA NIM catalog, additional Groq models, additional RunPod candidates)
-- gets added as rows when you actually go get them — next chapter.
INSERT INTO model_catalog (source, provider_key, model_name, role, status, notes) VALUES
  ('dslab', 'ollama_local', 'llama3.2:3b-instruct-q8_0', 'production', 'promoted',
   'Current production model per main.py ask_llm(). Also the first eval candidate tested.'),
  ('gemini_api', 'gemini_api', 'gemini-2.5-flash', 'judge_candidate', 'wired',
   'Primary judge as of 2026-07-12 (JUDGE_MATRIX order). Free tier, rate-limited.'),
  ('groq_api', 'groq_api', 'llama-3.3-70b-versatile', 'judge_candidate', 'wired',
   'Fallback judge if Gemini rate-limits. Confirm model id is still current before relying on it — Groq deprecates models fast.'),
  ('anthropic_api', 'anthropic_api', 'claude-haiku-4-5-20251001', 'judge_candidate', 'wired',
   'Third fallback judge. No API key configured yet as of 2026-07-12 — status is wired, not tested.');
