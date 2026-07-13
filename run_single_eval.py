"""Jarvis Core — single-provider eval run.

Use this when you only have one candidate available (e.g. RunPod is down
and you're testing dslab alone). compare_runpod_vs_dslab.py needs both
providers reachable; this doesn't.

Usage:
    python run_single_eval.py --provider ollama_local --model llama3.2:3b-instruct-q8_0

Default model matches what main.py already runs in production on dslab
(see ask_llm() in main.py) — testing that exact model first tells you
whether production's current bugs would even show up in this eval grid,
before you go comparing it against anything else.
"""

import argparse
import os

from dotenv import load_dotenv
from supabase import create_client

import llm_router
from eval_cases import KESARI_TEST_GRID
from eval_graph import build_eval_graph, new_run_id
from scorecard import generate_scorecard

load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=["ollama_local", "runpod_gpu"])
    parser.add_argument("--model", default="llama3.2:3b-instruct-q8_0",
                         help="Defaults to the exact model main.py runs in production today")
    parser.add_argument("--tenant-slug", default="keshri-pipes")
    parser.add_argument("--judge-provider", default=None, choices=["gemini_api", "groq_api", "anthropic_api"],
                         help="Force a single judge instead of the fallback chain (for debugging/comparison)")
    parser.add_argument("--out", default="single_run_scorecard.md")
    args = parser.parse_args()

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    providers = llm_router.default_providers()
    graph = build_eval_graph(providers, supabase)

    run_id = new_run_id()
    print(f"Running {len(KESARI_TEST_GRID)} cases against {args.provider} / {args.model} "
          f"(judge: {args.judge_provider or 'fallback chain'}) ...")
    for i, case in enumerate(KESARI_TEST_GRID, 1):
        state = graph.invoke({
            "run_id": run_id,
            "tenant_slug": args.tenant_slug,
            "test_case": case.__dict__,
            "candidate_provider": args.provider,
            "candidate_model": args.model,
            "judge_provider_override": args.judge_provider,
        })
        mark = "PASS" if state["verdict"] else "FAIL"
        print(f"  [{i}/{len(KESARI_TEST_GRID)}] {mark}  {case.label}")

    md = generate_scorecard(supabase, run_ids=[run_id])
    with open(args.out, "w") as f:
        f.write(md)
    print(f"\nWrote {args.out}")
    print(f"run_id: {run_id}")


if __name__ == "__main__":
    main()
