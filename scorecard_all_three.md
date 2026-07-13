# Jarvis Core — Eval Scorecard

_160 test-case results across 3 candidate(s)._


## ollama_local / llama3.2:3b-instruct-q8_0

- **Signal:** RED
- **Overall pass rate:** 18.3% (22/120)
- **Avg latency:** 2129ms
- **Hard failures (empty output / connection errors):** 0

| Category | Pass rate |
|---|---|
| happy_path | 20.8% |
| boundary | 20.8% |
| adversarial | 12.5% |
| out_of_distribution | 29.2% |
| regression | 8.3% |

| CRAFT dimension | Avg (1-3) |
|---|---|
| correctness | 1.42 |
| relevance | 1.43 |
| adherence | 1.42 |
| faithfulness | 1.43 |
| tone | 1.5 |

**Recommendation:** 🔴 RED — not safe for any unsupervised production traffic. Adversarial pass rate is only 12.5% — this model is easy to prompt-inject or manipulate into fake discounts/admin access. Do NOT use for agent_turn tasks that can take real actions (orders, payments) until this improves. Regression pass rate is 8.3% — at least one previously-fixed bug (language mixing, over-refusal, stale price data) has resurfaced. Investigate before promoting.


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
