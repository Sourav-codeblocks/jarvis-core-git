-- Jarvis Core — model_catalog migration: link catalog rows to real eval results
-- Run AFTER model_catalog_schema.sql already exists.

ALTER TABLE model_catalog ADD COLUMN IF NOT EXISTS signal TEXT
    CHECK (signal IN ('green', 'yellow', 'red') OR signal IS NULL);
ALTER TABLE model_catalog ADD COLUMN IF NOT EXISTS pass_rate NUMERIC(5,2);
ALTER TABLE model_catalog ADD COLUMN IF NOT EXISTS eval_run_id UUID;
ALTER TABLE model_catalog ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ;

-- Widen source list: together_ai wasn't in the original set from 2026-07-12
ALTER TABLE model_catalog DROP CONSTRAINT IF EXISTS model_catalog_source_check;
ALTER TABLE model_catalog ADD CONSTRAINT model_catalog_source_check
    CHECK (source IN (
        'dslab', 'runpod', 'together_ai', 'nvidia_nim',
        'anthropic_api', 'gemini_api', 'groq_api', 'other'
    ));
