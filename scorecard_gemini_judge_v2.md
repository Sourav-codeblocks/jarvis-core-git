# Jarvis Core — Eval Scorecard

_20 test-case results across 1 candidate(s)._


## ollama_local / llama3.2:3b-instruct-q8_0

- **Signal:** RED
- **Overall pass rate:** 55.0% (11/20)
- **Avg latency:** 2096ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 75.0% |
| boundary | 50.0% |
| adversarial | 50.0% |
| out_of_distribution | 75.0% |
| regression | 25.0% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 2.3 |
| relevance | 2.5 |
| adherence | 2.4 |
| faithfulness | 2.4 |
| tone | 2.5 |

**Recommendation:** 🔴 RED — not safe for any unsupervised production traffic. Adversarial pass rate is only 50.0% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 25.0% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.
