"""Jarvis Core — Eval subject: usage_events grounding.

Different shape of test than eval_cases.py's KESARI_TEST_GRID on purpose.
That grid is for the customer-facing catalog bot and checks static,
hand-labeled expected_keywords/forbidden_keywords — fine when the "right
answer" doesn't change between runs.

This subject is for the founder path's get_usage_report(), where the
whole point is that the model is talking about LIVE data. There is no
fixed golden answer to compare against — "how many LLM calls this week"
is a different real number every time this runs. So instead of keyword
matching, this:

  1. Computes ground truth by calling the exact same query the
     production code uses (founder_ws._usage_report_data), fresh, right
     before the test.
  2. Asks the model the question in several different phrasings.
  3. Extracts every integer the model states in its spoken answer.
  4. Fails the case if ANY stated number isn't one of the real numbers
     that just came back from the database (the total, or any single
     day's count). That's a direct hallucination check — no judge model,
     no subjective scoring, just "did it say a number that isn't real."

Usage:
    python eval_usage_grounding.py --tenant-slug keshri-pipes
    python eval_usage_grounding.py --tenant-slug keshri-pipes --persist
"""

import argparse
import asyncio
import os
import re
import uuid
from dataclasses import dataclass

from dotenv import load_dotenv

from db_client import resolve_tenant, get_supabase
import founder_ws

load_dotenv()


@dataclass
class UsageGroundingCase:
    label: str
    phrasing: str  # how the founder might actually ask, in their own words


# Deliberately varied phrasing — a model that's actually grounding on the
# tool result should give the same real numbers regardless of how casually
# or indirectly the question is asked. A model that's pattern-matching or
# confabulating tends to drift on the less direct phrasings.
USAGE_GROUNDING_CASES = [
    UsageGroundingCase(
        label="direct_count",
        phrasing="How many LLM calls have we made in the last 7 days?",
    ),
    UsageGroundingCase(
        label="casual_phrasing",
        phrasing="How's our usage looking lately?",
    ),
    UsageGroundingCase(
        label="today_only",
        phrasing="Did we get any AI calls today specifically?",
    ),
    UsageGroundingCase(
        label="hinglish_mix",
        phrasing="Pichle hafte kitne AI calls hue?",
    ),
]


async def run_case(case: UsageGroundingCase, tenant_id: int) -> dict:
    # Ground truth computed fresh, same query production runs — not a
    # fixture, not a stored value from an earlier session.
    ground_truth = founder_ws._usage_report_data(tenant_id)

    # Real numbers = every digit sequence in the EXACT text the model was
    # shown (via _usage_data_summary), not just the chart values. This
    # matters because that text also says "last 7 days" — a legitimate
    # number to repeat back, not a hallucination — and only comparing
    # against chart/total values would wrongly flag a correctly-grounded
    # answer for mentioning the time window.
    data_summary = founder_ws._usage_data_summary(ground_truth)
    real_numbers = set(re.findall(r"\b\d+\b", data_summary))

    result = await founder_ws.get_usage_report(tenant_id, user_text=case.phrasing)
    spoken = result.get("spokenAnswer", "")

    stated_numbers = set(re.findall(r"\b\d+\b", spoken))
    invented = stated_numbers - real_numbers

    passed = len(invented) == 0 and len(stated_numbers) > 0

    return {
        "label": case.label,
        "phrasing": case.phrasing,
        "ground_truth_total": ground_truth["total_calls"],
        "real_numbers": sorted(real_numbers, key=int),
        "spoken_answer": spoken,
        "stated_numbers": sorted(stated_numbers, key=int),
        "invented_numbers": sorted(invented, key=int),
        "passed": passed,
    }


async def run_all(tenant_slug: str) -> list[dict]:
    tenant = resolve_tenant(tenant_slug)
    return [await run_case(case, tenant["id"]) for case in USAGE_GROUNDING_CASES]


def persist_results(results: list[dict], tenant_slug: str, candidate_model: str) -> str:
    """Optional: write into the same llm_evaluations table eval_graph.py
    uses, under test_category='data_grounding'. Requires widening that
    table's CHECK constraint first — see
    eval_schema_add_grounding_category.sql. Wrapped so a missing
    migration doesn't crash the run; it just skips persistence.
    """
    supabase = get_supabase()
    run_id = str(uuid.uuid4())
    for r in results:
        try:
            supabase.table("llm_evaluations").insert({
                "run_id": run_id,
                "tenant_slug": tenant_slug,
                "test_label": r["label"],
                "test_category": "data_grounding",
                "input_text": r["phrasing"],
                "candidate_provider": "ollama_local",
                "candidate_model": candidate_model,
                "raw_output": r["spoken_answer"],
                "generation_error": None,
                "latency_ms": None,
                "tier1_result": {
                    "ground_truth_total": r["ground_truth_total"],
                    "real_numbers": r["real_numbers"],
                    "stated_numbers": r["stated_numbers"],
                    "invented_numbers": r["invented_numbers"],
                },
                "tier2_result": {},
                "passed": r["passed"],
            }).execute()
        except Exception as err:
            print(f"  (persist skipped for {r['label']}: {err})")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test whether the founder-path LLM ever states a number "
                     "that isn't in the real usage_events query result."
    )
    parser.add_argument("--tenant-slug", default=os.environ.get("TENANT_SLUG", "keshri-pipes"))
    parser.add_argument("--persist", action="store_true",
                         help="Also write results to llm_evaluations (needs the "
                              "widened test_category constraint, see the .sql file)")
    args = parser.parse_args()

    results = asyncio.run(run_all(args.tenant_slug))

    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} passed — usage_events grounding\n")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL — HALLUCINATION"
        print(f"[{status}] {r['label']}: \"{r['phrasing']}\"")
        print(f"    real numbers available : {r['real_numbers']}")
        print(f"    spoken answer          : {r['spoken_answer']!r}")
        print(f"    numbers it stated      : {r['stated_numbers']}")
        if r["invented_numbers"]:
            print(f"    >>> INVENTED, NOT IN REAL DATA: {r['invented_numbers']}")
        print()

    if args.persist:
        run_id = persist_results(results, args.tenant_slug, candidate_model="qwen2.5:7b-instruct-q8_0")
        print(f"Persisted under run_id: {run_id}")

    if passed < len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
