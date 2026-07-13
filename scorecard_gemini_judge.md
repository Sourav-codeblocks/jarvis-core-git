# Jarvis Core — Eval Scorecard

_20 test-case results across 1 candidate(s)._


## ollama_local / llama3.2:3b-instruct-q8_0

- **Signal:** RED
- **Overall pass rate:** 0.0% (0/20)
- **Avg latency:** 1717ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 0.0% |
| boundary | 0.0% |
| adversarial | 0.0% |
| out_of_distribution | 0.0% |
| regression | 0.0% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 1.0 |
| relevance | 1.0 |
| adherence | 1.0 |
| faithfulness | 1.0 |
| tone | 1.0 |

**Recommendation:** 🔴 RED — not safe for any unsupervised production traffic. Adversarial pass rate is only 0.0% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 0.0% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting. Fast (1717ms avg) — a reasonable candidate for the 'intent' task_type slot.
