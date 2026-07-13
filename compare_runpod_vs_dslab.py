"""Jarvis Core — RunPod vs dslab one-off comparison.

Run this directly, no FastAPI server needed. Requires:
  - the dslab SSH tunnel open (COMMANDS.md): ssh -L 11434:localhost:11434 teaching@172.18.40.103
  - RUNPOD_ENDPOINT_URL set to the pod's public proxy URL
  - SUPABASE_URL / SUPABASE_SECRET_KEY in .env
  - eval_schema.sql already run against Supabase (creates llm_evaluations)

Usage:
    python compare_runpod_vs_dslab.py --model llama3.2:3b

Same model name is assumed to exist on both boxes. If the RunPod pod is
serving a differently-named model, pass --runpod-model separately.
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


def run_grid(graph, run_id: str, tenant_slug: str, provider: str, model: str):
    for case in KESARI_TEST_GRID:
        graph.invoke({
            "run_id": run_id,
            "tenant_slug": tenant_slug,
            "test_case": case.__dict__,
            "candidate_provider": provider,
            "candidate_model": model,
        })
    print(f"  done: {provider} / {model} ({len(KESARI_TEST_GRID)} cases)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Model name, assumed same on both boxes unless overridden")
    parser.add_argument("--runpod-model", default=None)
    parser.add_argument("--dslab-model", default=None)
    parser.add_argument("--tenant-slug", default="keshri-pipes")
    parser.add_argument("--out", default="comparison_scorecard.md")
    args = parser.parse_args()

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    providers = llm_router.default_providers()
    graph = build_eval_graph(providers, supabase)

    runpod_model = args.runpod_model or args.model
    dslab_model = args.dslab_model or args.model

    print(f"Running grid against RunPod ({runpod_model})...")
    runpod_run_id = new_run_id()
    run_grid(graph, runpod_run_id, args.tenant_slug, "runpod_gpu", runpod_model)

    print(f"Running grid against dslab ({dslab_model})...")
    dslab_run_id = new_run_id()
    run_grid(graph, dslab_run_id, args.tenant_slug, "ollama_local", dslab_model)

    print("Generating comparison scorecard...")
    md = generate_scorecard(supabase, run_ids=[runpod_run_id, dslab_run_id])
    with open(args.out, "w") as f:
        f.write(md)
    print(f"\nWrote {args.out} — open it to compare RunPod vs dslab side by side.")
    print(f"run_ids for reference: runpod={runpod_run_id} dslab={dslab_run_id}")


if __name__ == "__main__":
    main()
