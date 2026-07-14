"""Founder's Core — real data reports (Phase 1).

Replaces the Lovable-generated mock FOUNDER_REPORTS. Kesari Pipes has no
revenue/deals table yet, so what's real right now is Jarvis Core's own
operational data: usage volume, cost/latency, switchbox status, customer
roster. Add a real revenue/orders table later and wire a fifth report in
here with the same OverlayPayload shape — nothing downstream changes.
"""

from datetime import datetime, timedelta, timezone

TENANT_ID = 1  # Phase 0: single tenant, same seam as everywhere else in main.py


def _overlay(kind: str, title: str, **kw) -> dict:
    return {"kind": kind, "title": title, **kw}


def usage_report(supabase) -> dict:
    """Agent turn volume, last 7 days — from usage_events."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = (
        supabase.table("usage_events")
        .select("created_at")
        .eq("tenant_id", TENANT_ID)
        .gte("created_at", since)
        .execute()
        .data
    )
    buckets: dict[str, int] = {}
    for r in rows:
        day = r["created_at"][:10]
        buckets[day] = buckets.get(day, 0) + 1
    chart = [{"label": d[-2:], "value": v} for d, v in sorted(buckets.items())]
    total = sum(buckets.values())
    spoken = (
        f"{total} agent turns in the last seven days."
        if total
        else "No agent turns logged in the last seven days yet."
    )
    return {
        "id": "usage",
        "label": "Usage",
        "hint": "7-day agent turns",
        "spokenAnswer": spoken,
        "overlay": _overlay("chart", "Agent Turns · Last 7 Days", chart=chart),
    }


def cost_report(supabase) -> dict:
    """Spend, latency, local-vs-cloud split, last 24h — from usage_events."""
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    rows = (
        supabase.table("usage_events")
        .select("cost_usd, latency_ms, provider")
        .eq("tenant_id", TENANT_ID)
        .gte("created_at", since)
        .execute()
        .data
    )
    n = len(rows)
    total_cost = sum(r["cost_usd"] or 0 for r in rows)
    avg_latency = int(sum(r["latency_ms"] or 0 for r in rows) / n) if n else 0
    cloud_calls = sum(1 for r in rows if r["provider"] not in ("ollama_dslab", "ollama_local"))
    local_pct = int(100 * (1 - cloud_calls / n)) if n else 100
    spoken = (
        f"Spent ${total_cost:.4f} in the last 24 hours, average latency "
        f"{avg_latency} milliseconds, {local_pct}% served locally."
    )
    return {
        "id": "cost",
        "label": "Cost & Latency",
        "hint": "24h run rate",
        "spokenAnswer": spoken,
        "overlay": _overlay(
            "gauge",
            "Cost & Latency · Last 24h",
            gauges=[
                {"label": "COST", "value": round(total_cost, 4), "max": max(round(total_cost, 4), 1), "unit": "$"},
                {"label": "AVG LATENCY", "value": avg_latency, "max": max(avg_latency, 2000), "unit": "ms"},
                {"label": "LOCAL SERVED", "value": local_pct, "max": 100, "unit": "%"},
                {"label": "CALLS", "value": n, "max": max(n, 10), "unit": ""},
            ],
        ),
    }


def switchbox_report(supabase) -> dict:
    """Live tenant_tools status — the actual switchbox, not a mock of it."""
    rows = (
        supabase.table("tenant_tools")
        .select("tool_key, enabled, tier_required")
        .eq("tenant_id", TENANT_ID)
        .execute()
        .data
    )
    enabled_count = sum(1 for r in rows if r["enabled"])
    table_rows = [
        {
            "status": "resolved" if r["enabled"] else "pending",
            "cells": [r["tool_key"], "ON" if r["enabled"] else "OFF", r["tier_required"]],
        }
        for r in rows
    ]
    spoken = f"{enabled_count} of {len(rows)} tools enabled for this tenant."
    return {
        "id": "switchbox",
        "label": "Switchbox",
        "hint": "Tool status",
        "spokenAnswer": spoken,
        "overlay": _overlay(
            "table", "Tenant Tools", table={"columns": ["Tool", "Status", "Tier"], "rows": table_rows}
        ),
    }


def customers_report(supabase) -> dict:
    """Roster snapshot — from users. No CRM/deals data exists yet, this is real."""
    recent = (
        supabase.table("users")
        .select("display_name, reputation, created_at")
        .eq("tenant_id", TENANT_ID)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
    )
    all_rows = supabase.table("users").select("id, reputation").eq("tenant_id", TENANT_ID).execute().data
    total = len(all_rows)
    avg_rep = int(sum(r["reputation"] for r in all_rows) / total) if total else 0
    lines = [f"// {r['display_name'] or 'Unknown'} — reputation {r['reputation']}" for r in recent]
    spoken = f"{total} customers on record, average reputation {avg_rep}."
    return {
        "id": "customers",
        "label": "Customers",
        "hint": "Recent signups",
        "spokenAnswer": spoken,
        "overlay": _overlay("report", "Recent Customers", report=lines or ["// No customers yet."]),
    }


REPORT_FUNCS = {
    "usage": usage_report,
    "cost": cost_report,
    "switchbox": switchbox_report,
    "customers": customers_report,
}

# Cheap keyword routing for the voice/type query box, until this goes through
# llm_router's escalation task_type for real NLP intent classification.
KEYWORDS = {
    "usage": ["usage", "volume", "turns", "traffic", "activity"],
    "cost": ["cost", "spend", "latency", "money", "run rate", "budget"],
    "switchbox": ["switchbox", "tools", "tool", "integrations", "channels"],
    "customers": ["customer", "customers", "users", "signup", "roster"],
}


def get_all_reports(supabase) -> list[dict]:
    return [fn(supabase) for fn in REPORT_FUNCS.values()]


def get_report(supabase, report_id: str) -> dict | None:
    fn = REPORT_FUNCS.get(report_id)
    return fn(supabase) if fn else None


def route_query(query: str) -> str:
    q = query.lower()
    for report_id, words in KEYWORDS.items():
        if any(w in q for w in words):
            return report_id
    return "usage"  # sensible default when nothing matches
