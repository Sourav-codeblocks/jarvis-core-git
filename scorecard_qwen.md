# Jarvis Core — Eval Scorecard

_20 test-case results across 1 candidate(s)._


## ollama_local / qwen2.5:7b-instruct-q8_0

- **Signal:** YELLOW
- **Overall pass rate:** 75.0% (15/20)
- **Avg latency:** 2809ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 100.0% |
| boundary | 75.0% |
| adversarial | 50.0% |
| out_of_distribution | 100.0% |
| regression | 50.0% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 2.6 |
| relevance | 2.4 |
| adherence | 2.55 |
| faithfulness | 2.6 |
| tone | 2.75 |

**Recommendation:** 🟡 YELLOW — usable for supervised or read-only tasks only. Do NOT give this model agent_turn access to orders, discounts, or payments yet. Adversarial pass rate is only 50.0% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 50.0% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.
