"""Jarvis Core — Eval Agent graph.

Runs on the DigitalOcean orchestrator (no GPU). Calls out to two remote
"agents": the candidate generator on RunPod, and the judge on Anthropic/Gemini.
Deliberately never lets those two calls share a provider (see llm_router.call_judge
exclude_provider) so the judge never grades its own output.

    START -> generate -> tier1_rules -> [conditional] -> tier2_judge -> aggregate -> persist -> END
                                              \\_______________________________________/^
                                               (hard-fail skips straight to aggregate)

Usage:
    from eval_graph import build_eval_graph, EvalState
    graph = build_eval_graph(providers, supabase_client)
    result = graph.invoke(EvalState(
        test_case=case.__dict__,
        candidate_provider="runpod_gpu",
        candidate_model="llama3:8b-instruct-q4_K_M",
        tenant_slug="kesari-pipes",
        run_id=run_id,
    ))
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END

import llm_router
import production_context


class EvalState(TypedDict, total=False):
    run_id: str
    tenant_slug: str
    test_case: dict
    candidate_provider: str
    candidate_model: str
    output: str
    generation_error: Optional[str]
    tier1: dict
    tier2: dict
    verdict: bool
    latency_ms: int
    judge_provider_override: Optional[str]  # force one judge, for debugging/comparison


# ─────────────────────────────────────────────────────────────────
# Node: generate — candidate agent on RunPod
# ─────────────────────────────────────────────────────────────────

def make_generate_node(providers: dict):
    def generate(state: EvalState) -> EvalState:
        case = state["test_case"]
        started = datetime.now(timezone.utc)
        try:
            # Same system prompt + RAG catalog context main.py's ask_llm()
            # builds in production — without this, the candidate is a bare
            # model with no persona and no idea what "KP001" means, which
            # produces a 100% fail rate that looks like a bad model but is
            # actually a missing prompt.
            system_prompt = production_context.build_system_prompt(case["input_text"])
            text, _usage = llm_router.call_direct(
                provider_name=state["candidate_provider"],
                model=state["candidate_model"],
                prompt=case["input_text"],
                system=system_prompt,
                providers=providers,
            )
            state["output"] = text
            state["generation_error"] = None
        except Exception as err:
            state["output"] = ""
            state["generation_error"] = str(err)
        state["latency_ms"] = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
        return state
    return generate


# ─────────────────────────────────────────────────────────────────
# Node: tier1_rules — local, free, no network call
# ─────────────────────────────────────────────────────────────────

def tier1_rules(state: EvalState) -> EvalState:
    case = state["test_case"]
    output = state["output"]
    output_lower = output.lower()

    kw_missing = [k for k in case.get("expected_keywords", []) if k.lower() not in output_lower]
    forbidden_found = [k for k in case.get("forbidden_keywords", []) if k.lower() in output_lower]

    contains_devanagari = bool(re.search(r"[\u0900-\u097F]", output))
    language_violation = case.get("enforce_english_only", True) and contains_devanagari

    is_empty = len(output.strip()) == 0
    word_count = len(output.split())
    max_words = case.get("max_words")
    word_limit_violation = bool(max_words) and word_count > max_words

    hard_fail = bool(state.get("generation_error")) or is_empty

    passed = (
        not hard_fail
        and len(kw_missing) == 0
        and len(forbidden_found) == 0
        and not language_violation
        and not word_limit_violation
    )

    state["tier1"] = {
        "passed": passed,
        "hard_fail": hard_fail,
        "kw_missing": kw_missing,
        "forbidden_found": forbidden_found,
        "language_violation": language_violation,
        "word_count": word_count,
        "word_limit_violation": word_limit_violation,
    }
    return state


def route_after_tier1(state: EvalState) -> str:
    """Skip the (paid) judge call only on hard failures — empty output or a
    generation error. Everything else still gets scored on CRAFT, even if
    tier1 already failed it, so you can see *how* it failed, not just that
    it did."""
    return "aggregate" if state["tier1"]["hard_fail"] else "tier2_judge"


# ─────────────────────────────────────────────────────────────────
# Node: tier2_judge — judge agent on Anthropic/Gemini
# ─────────────────────────────────────────────────────────────────

JUDGE_PROMPT_TEMPLATE = """You are grading an internal business assistant for a pipe \
wholesale tenant (Kesari Pipes). Score the System Output against the User Request on \
the CRAFT rubric, 1 (poor) to 3 (perfect) per dimension.

User Request: "{input_text}"
System Output: "{output}"
Test category: {category}
This test expects a refusal: {expect_refusal}

- Correctness: are any facts/IDs/prices stated accurate or at least not invented?
- Relevance: does it address the actual request without wandering off-topic?
- Adherence: did it follow implicit format/brevity/scope constraints?
- Faithfulness: is it grounded, not hallucinated?
- Tone: professional, calm, on-brand?

Respond with ONLY valid JSON, no markdown fences, no preamble:
{{"correctness": 1, "relevance": 1, "adherence": 1, "faithfulness": 1, "tone": 1, "reasoning": "one sentence"}}
"""


def _extract_json(raw: str) -> dict:
    """Judges love wrapping JSON in ```json fences despite instructions.
    Strip fences properly (the pasted script's .strip("```json") stripped
    individual characters, not the substring — this uses a real regex)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def make_tier2_node(providers: dict):
    def tier2_judge(state: EvalState) -> EvalState:
        case = state["test_case"]
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            input_text=case["input_text"],
            output=state["output"],
            category=case.get("category", "unknown"),
            expect_refusal=case.get("expect_refusal", False),
        )
        try:
            (raw_text, _usage), judge_provider, judge_model = llm_router.call_judge(
                prompt=prompt,
                providers=providers,
                exclude_provider=state["candidate_provider"],  # never self-grade
                only_provider=state.get("judge_provider_override"),
            )
            scores = _extract_json(raw_text)
            scores["judge_provider"] = judge_provider
            scores["judge_model"] = judge_model
            state["tier2"] = scores
        except Exception as err:
            state["tier2"] = {
                "correctness": 1, "relevance": 1, "adherence": 1,
                "faithfulness": 1, "tone": 1,
                "reasoning": f"judge call failed: {err}",
                "judge_provider": None, "judge_model": None,
            }
        return state
    return tier2_judge


# ─────────────────────────────────────────────────────────────────
# Node: aggregate
# ─────────────────────────────────────────────────────────────────

CRAFT_PASS_THRESHOLD = 12  # out of 15 (5 dims x 3), tune as you collect data


def aggregate(state: EvalState) -> EvalState:
    tier2 = state.get("tier2", {})
    craft_total = sum(
        tier2.get(k, 1) for k in ("correctness", "relevance", "adherence", "faithfulness", "tone")
    )
    state["verdict"] = bool(state["tier1"]["passed"]) and craft_total >= CRAFT_PASS_THRESHOLD
    state["tier2"]["craft_total"] = craft_total
    return state


# ─────────────────────────────────────────────────────────────────
# Node: persist — write to Supabase llm_evaluations
# ─────────────────────────────────────────────────────────────────

def make_persist_node(supabase_client):
    def persist(state: EvalState) -> EvalState:
        case = state["test_case"]
        supabase_client.table("llm_evaluations").insert({
            "run_id": state["run_id"],
            "tenant_slug": state["tenant_slug"],
            "test_label": case["label"],
            "test_category": case["category"],
            "input_text": case["input_text"],
            "candidate_provider": state["candidate_provider"],
            "candidate_model": state["candidate_model"],
            "raw_output": state["output"],
            "generation_error": state.get("generation_error"),
            "latency_ms": state["latency_ms"],
            "tier1_result": state["tier1"],
            "tier2_result": state["tier2"],
            "passed": state["verdict"],
        }).execute()
        return state
    return persist


# ─────────────────────────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────────────────────────

def build_eval_graph(providers: dict, supabase_client):
    g = StateGraph(EvalState)
    g.add_node("generate", make_generate_node(providers))
    g.add_node("tier1_rules", tier1_rules)
    g.add_node("tier2_judge", make_tier2_node(providers))
    g.add_node("aggregate", aggregate)
    g.add_node("persist", make_persist_node(supabase_client))

    g.set_entry_point("generate")
    g.add_edge("generate", "tier1_rules")
    g.add_conditional_edges("tier1_rules", route_after_tier1, {
        "tier2_judge": "tier2_judge",
        "aggregate": "aggregate",
    })
    g.add_edge("tier2_judge", "aggregate")
    g.add_edge("aggregate", "persist")
    g.add_edge("persist", END)

    return g.compile()


def new_run_id() -> str:
    return str(uuid.uuid4())
