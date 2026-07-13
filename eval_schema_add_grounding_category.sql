-- Widens llm_evaluations.test_category to allow 'data_grounding' —
-- the numeric-hallucination check eval_usage_grounding.py runs against
-- founder_ws.get_usage_report(). Optional: only needed if you pass
-- --persist to eval_usage_grounding.py.
--
-- Run this against the same Supabase project eval_schema.sql already ran against.

ALTER TABLE llm_evaluations DROP CONSTRAINT IF EXISTS llm_evaluations_test_category_check;

ALTER TABLE llm_evaluations ADD CONSTRAINT llm_evaluations_test_category_check
    CHECK (test_category IN (
        'happy_path', 'boundary', 'adversarial',
        'out_of_distribution', 'regression',
        'data_grounding'
    ));
