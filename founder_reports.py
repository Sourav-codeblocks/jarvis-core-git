"""Founder's Core — REST report endpoints (main.py's /api/founder/* routes).

This was missing from disk entirely, which meant main.py couldn't even
be imported (see PROGRESS.md, 2026-07-13 session 3). It's a thin,
synchronous wrapper around founder_ws.FOUNDER_TOOLS — the exact same
functions the WebSocket/voice path calls — so the REST dashboard and
the voice HUD always return identical data for the same report. One
source of truth per report, never two implementations that can drift.

route_query() here is a cheap keyword match, not an LLM call — it's a
lighter-weight fallback for simple dashboard-style queries. The
WebSocket path (founder_ws.route_founder_query) does real tool-calling
via qwen2.5 and should be preferred wherever a persistent connection is
available.
"""

import os

from db_client import resolve_tenant
from founder_ws import FOUNDER_TOOLS

TENANT_SLUG = os.environ.get("TENANT_SLUG", "keshri-pipes")


def _tenant_id() -> int:
    return resolve_tenant(TENANT_SLUG)["id"]


def get_all_reports(supabase) -> dict:
    """Every report the founder can pull, with fresh data for each.

    `supabase` is accepted (matches main.py's call signature) but not
    used directly here — FOUNDER_TOOLS' functions already hold their
    own client. Kept as a parameter so main.py doesn't need to change
    if these ever need the caller's client instead.
    """
    tenant_id = _tenant_id()
    reports = {}
    for report_id, tool in FOUNDER_TOOLS.items():
        try:
            reports[report_id] = tool(tenant_id)
        except Exception as err:
            print(f"founder_reports.get_all_reports: {report_id} failed: {err}")
            reports[report_id] = {
                "spokenAnswer": "This report is unavailable right now.",
                "overlay": None,
            }
    return reports


def get_report(supabase, report_id: str) -> dict | None:
    tool = FOUNDER_TOOLS.get(report_id)
    if not tool:
        return None
    return tool(_tenant_id())


# Keyword -> report_id, for the no-LLM REST fallback path.
_REPORT_KEYWORDS = {
    "get_revenue_report": ["revenue", "sales", "income"],
    "get_runway_report": ["runway", "burn", "cash", "margin"],
    "get_pipeline_report": ["pipeline", "deal", "deals", "lead", "leads"],
    "get_usage_report": ["usage", "llm", "api calls", "cost"],
    "get_catalog_report": ["catalog", "product", "stock", "inventory"],
    "get_briefing_report": ["briefing", "summary", "morning", "overview", "highlights"],
}


def route_query(query: str) -> str:
    """Cheapest possible match for the REST path. Falls back to the
    briefing report (a real, always-answerable summary) if nothing
    matches, rather than guessing at a more specific report."""
    q = query.lower()
    for report_id, keywords in _REPORT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return report_id
    return "get_briefing_report"
