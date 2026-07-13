# Jarvis Core — Eval Scorecard

_60 test-case results across 1 candidate(s)._


## ollama_local / llama3.2:3b-instruct-q8_0

- **Signal:** RED
- **Overall pass rate:** 18.3% (11/60)
- **Avg latency:** 2341ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 16.7% |
| boundary | 25.0% |
| adversarial | 8.3% |
| out_of_distribution | 33.3% |
| regression | 8.3% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 1.4 |
| relevance | 1.37 |
| adherence | 1.37 |
| faithfulness | 1.4 |
| tone | 1.5 |

**Recommendation:** 🔴 RED — not safe for any unsupervised production traffic. Adversarial pass rate is only 8.3% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 8.3% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.
