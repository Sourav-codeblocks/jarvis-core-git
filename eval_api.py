"""Jarvis Core — Eval orchestrator API.

Runs on the DigitalOcean VM (no GPU, always-on). This is deliberately a
SEPARATE FastAPI app from main.py's production gateway — Phase 1 of the
original ask was "out-of-band from production traffic," and mounting this
on the same app as the Telegram webhook would violate that the first time
someone accidentally shares a worker pool or a slow eval sweep blocks a
production request.

Deploy as its own process:
    uvicorn eval_api:app --host 0.0.0.0 --port 8100

Endpoints:
    POST /eval/run                 -> kicks off a full test-grid sweep for one
                                       candidate model on RunPod, returns run_id
    GET  /eval/readiness/{model}   -> aggregate stats + READY_FOR_PRODUCTION verdict
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client

import llm_router
from eval_cases import KESARI_TEST_GRID
from eval_graph import build_eval_graph, new_run_id
from scorecard import generate_scorecard

load_dotenv()

app = FastAPI(title="Jarvis Core Eval Orchestrator")

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

providers = llm_router.default_providers()
graph = build_eval_graph(providers, supabase)

READINESS_PASS_RATE = 0.90  # >90% of the grid, matches the original ask


class RunRequest(BaseModel):
    tenant_slug: str = "keshri-pipes"
    candidate_provider: str = "runpod_gpu"
    candidate_model: str


@app.post("/eval/run")
def run_eval(req: RunRequest):
    """Synchronous for now (Phase 0.5) — 20 cases against a RunPod candidate
    plus judge calls takes on the order of a minute or two. Move to a
    background task / queue once eval volume or grid size grows."""
    run_id = new_run_id()
    results = []
    for case in KESARI_TEST_GRID:
        state = graph.invoke({
            "run_id": run_id,
            "tenant_slug": req.tenant_slug,
            "test_case": case.__dict__,
            "candidate_provider": req.candidate_provider,
            "candidate_model": req.candidate_model,
        })
        results.append({"label": case.label, "passed": state["verdict"]})

    passed = sum(1 for r in results if r["passed"])
    return {
        "run_id": run_id,
        "candidate_model": req.candidate_model,
        "total_cases": len(results),
        "passed_cases": passed,
        "pass_rate": round(passed / len(results), 4),
        "results": results,
    }


@app.get("/eval/readiness/{candidate_model}")
def readiness(candidate_model: str, tenant_slug: str = "keshri-pipes", recent_runs: int = 1):
    """Model readiness gate for the admin panel. Looks at the most recent
    `recent_runs` run_ids for this candidate and computes aggregate stats."""
    run_rows = (
        supabase.table("llm_evaluations")
        .select("run_id, created_at")
        .eq("tenant_slug", tenant_slug)
        .eq("candidate_model", candidate_model)
        .order("created_at", desc=True)
        .limit(200)  # enough rows to find recent_runs distinct run_ids from
        .execute()
    )
    if not run_rows.data:
        raise HTTPException(404, f"No eval runs found for {candidate_model}")

    seen_runs = []
    for row in run_rows.data:
        if row["run_id"] not in seen_runs:
            seen_runs.append(row["run_id"])
        if len(seen_runs) >= recent_runs:
            break

    rows = (
        supabase.table("llm_evaluations")
        .select("*")
        .in_("run_id", seen_runs)
        .execute()
    ).data

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    avg_latency = sum(r["latency_ms"] or 0 for r in rows) / total if total else 0
    regression_rows = [r for r in rows if r["test_category"] == "regression"]
    regression_passed = sum(1 for r in regression_rows if r["passed"])

    pass_rate = passed / total if total else 0
    ready = pass_rate >= READINESS_PASS_RATE

    from scorecard import _signal  # reuse the exact same logic as the scorecard, one source of truth
    category_pass_rate = {}
    for cat in ["happy_path", "boundary", "adversarial", "out_of_distribution", "regression"]:
        cat_rows = [r for r in rows if r["test_category"] == cat]
        if cat_rows:
            cat_passed = sum(1 for r in cat_rows if r["passed"])
            category_pass_rate[cat] = round(100 * cat_passed / len(cat_rows), 1)
    signal = _signal({"overall_pass_rate": round(100 * pass_rate, 1), "category_pass_rate": category_pass_rate})

    return {
        "candidate_model": candidate_model,
        "tenant_slug": tenant_slug,
        "runs_considered": seen_runs,
        "total_cases": total,
        "pass_rate": round(pass_rate, 4),
        "signal": signal,  # green | yellow | red — see scorecard.py for what each means
        "avg_latency_ms": round(avg_latency, 1),
        "regression_pass_rate": round(regression_passed / len(regression_rows), 4) if regression_rows else None,
        "READY_FOR_PRODUCTION": ready,  # kept for backward compat; `signal` carries more nuance
        "threshold": READINESS_PASS_RATE,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/eval/scorecard")
def scorecard(run_ids: str | None = None, tenant_slug: str | None = None):
    """run_ids: comma-separated list, e.g. ?run_ids=uuid1,uuid2
    Omit run_ids to include everything (careful once volume grows)."""
    ids = run_ids.split(",") if run_ids else None
    md = generate_scorecard(supabase, run_ids=ids, tenant_slug=tenant_slug)
    return {"markdown": md}


@app.get("/health")
def health():
    return {"orchestrator": "alive", "providers_configured": list(providers.keys())}
