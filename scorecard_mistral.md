# Jarvis Core — Eval Scorecard

_20 test-case results across 1 candidate(s)._


## ollama_local / mistral:7b-instruct-q8_0

- **Signal:** RED
- **Overall pass rate:** 30.0% (6/20)
- **Avg latency:** 3302ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 50.0% |
| boundary | 50.0% |
| adversarial | 0.0% |
| out_of_distribution | 0.0% |
| regression | 50.0% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 1.8 |
| relevance | 1.6 |
| adherence | 1.4 |
| faithfulness | 1.8 |
| tone | 2.1 |

**Recommendation:** 🔴 RED — not safe for any unsupervised production traffic. Adversarial pass rate is only 0.0% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 50.0% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.
