"""Jarvis Core — mark a model_catalog row from a completed eval run.

Today this is manual: you run an eval (run_single_eval.py etc.), then run
this with the resulting run_id. This is deliberately the seed of the future
"manual run architecture with buttons" — same underlying operation
(run_id -> stats -> catalog update), just triggered by hand for now.

Usage:
    python catalog_from_run.py --run-id <uuid> --role candidate
"""

import argparse
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

from scorecard import compute_stats

load_dotenv()

PROVIDER_TO_SOURCE = {
    "ollama_local": "dslab",
    "runpod_gpu": "runpod",
    "together_api": "together_ai",
    "nim_api": "nvidia_nim",
    "anthropic_api": "anthropic_api",
    "gemini_api": "gemini_api",
    "groq_api": "groq_api",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--role", default="candidate", choices=["candidate", "judge_candidate", "production"])
    args = parser.parse_args()

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    rows = supabase.table("llm_evaluations").select("*").eq("run_id", args.run_id).execute().data
    if not rows:
        print(f"No rows found for run_id {args.run_id}")
        return

    provider = rows[0]["candidate_provider"]
    model = rows[0]["candidate_model"]
    source = PROVIDER_TO_SOURCE.get(provider, "other")

    stats = compute_stats(rows)

    result = supabase.table("model_catalog").upsert({
        "source": source,
        "provider_key": provider,
        "model_name": model,
        "role": args.role,
        "status": "evaluated",
        "signal": stats["signal"],
        "pass_rate": stats["overall_pass_rate"],
        "eval_run_id": args.run_id,
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
        "notes": f"Auto-updated from run {args.run_id}: {stats['passed']}/{stats['total']} "
                 f"({stats['overall_pass_rate']}%), signal={stats['signal']}",
    }, on_conflict="source,model_name").execute()

    print(f"Marked {source}/{model} as {stats['signal'].upper()} "
          f"({stats['overall_pass_rate']}%, {stats['passed']}/{stats['total']})")


if __name__ == "__main__":
    main()
