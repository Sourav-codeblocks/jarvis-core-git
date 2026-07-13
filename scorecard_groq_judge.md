# Jarvis Core — Eval Scorecard

_20 test-case results across 1 candidate(s)._


## ollama_local / llama3.2:3b-instruct-q8_0

- **Overall pass rate:** 55.0% (11/20)
- **Avg latency:** 2332ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 50.0% |
| boundary | 75.0% |
| adversarial | 25.0% |
| out_of_distribution | 100.0% |
| regression | 25.0% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 2.2 |
| relevance | 2.1 |
| adherence | 2.1 |
| faithfulness | 2.2 |
| tone | 2.5 |

**Recommendation:** Low pass rate — not ready for any production traffic yet. Adversarial pass rate is only 25.0% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 25.0% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.
