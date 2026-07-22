"""Founder's Core bridge — WebSocket endpoint for the founder-facing HUD.

Routing is now real tool-calling via qwen2.5:7b (local, through Ollama) —
the model decides which founder tool answers a question based on meaning,
not a hardcoded keyword match. Model choice matches llm_router.py's
agent_turn local tier: kesari-pipes is a basic-tier tenant, and
TIER_ALLOWS_CLOUD["basic"] is False there, so this stays local-only,
consistent with the existing routing matrix.

(This bridge doesn't call llm_router.route() directly — that function
expects a caller-supplied `providers` dict and usage_logger this Phase 0
bridge doesn't wire up yet. Worth consolidating once usage_events logging
is added here too.)

No toleration middleware on this path — founder-only, not customer-facing.

Wiring: import this router into main.py and mount it —
    from founder_ws import router as founder_router
    app.include_router(founder_router)
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db_client import get_supabase, resolve_tenant, UnknownTenant

load_dotenv()  # self-sufficient — don't depend on main.py's import order

router = APIRouter()

supabase = get_supabase()  # shared client, same instance main.py and db_client use

_chroma = chromadb.PersistentClient(path="chroma_db")
_catalog_collections: dict[str, "chromadb.Collection"] = {}


def _get_catalog(collection_name: str):
    """Lazy-loaded, per-tenant, and cached by collection name so importing
    this module doesn't blow up if chroma_db or the collection isn't there
    yet. Same collections ingest.py populates and main.py's RAG path
    already queries.

    Was hardcoded to "kb_keshri_pipes" — fine while there was exactly one
    tenant, but it meant every tenant's founder catalog search would have
    silently searched tenant #1's data. Callers now pass the tenant's own
    `chroma_collection` value (resolved via db_client.resolve_tenant).

    NOTE: schema.sql's seed row says "kb_kesari_pipes" while the collection
    actually populated on disk (per PROGRESS.md / ingest.py runs) is
    "kb_keshri_pipes" — the spelling mismatch code_review.md already
    flagged (build-queue item 5, not fixed here). Align the DB row before
    relying on this for a real second tenant.
    """
    if collection_name not in _catalog_collections:
        _catalog_collections[collection_name] = _chroma.get_collection(
            name=collection_name,
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )
    return _catalog_collections[collection_name]


import asyncio

import llm_router
import providers

# Tool-deciding call needs real function-calling (structured tool_calls
# back, not just text) — see providers.get_raw_chat_call. Groq is listed
# first and alone for now: it's the certified, confirmed-working
# tool-calling candidate (PROGRESS.md 2026-07-13 — tool-call format OK,
# 336ms). ollama_local/dslab was the previous default but RunPod
# (xl0rixu7dkzh1b) was abandoned entirely per that same session; add it
# back to this list once a real local GPU is reachable again — same
# "TEMP, revert once local is reliable" pattern main.py's CLOUD_PROVIDERS
# already uses.
TOOL_CALL_CHAIN = [("groq", "llama-3.3-70b-versatile")]

# Plain-text synthesis (no tools) goes through llm_router.route()'s
# existing agent_turn chain instead of a hardcoded single provider — same
# Groq/Gemini fallback main.py's ask_llm() already uses.
_TEXT_PROVIDERS = {
    name: (lambda n: lambda model, prompt, timeout: providers.get_provider_call(n, model)(prompt, timeout))(name)
    for name in ("groq", "gemini")
}


def _usage_logger_for(tenant: dict):
    def usage_logger(task_type, model, provider, latency_ms, **usage):
        try:
            supabase.table("usage_events").insert({
                "tenant_id": tenant["id"],
                "task_type": task_type,
                "model": model,
                "provider": provider,
                "latency_ms": latency_ms,
                **usage,
            }).execute()
        except Exception as err:
            print(f"founder usage_events logging failed (non-fatal): {err}")
    return usage_logger

# --- Founder tool registry -------------------------------------------------
# Phase 0 stand-ins with the exact payload shape the frontend already
# expects (see dataAdapter.ts OverlayPayload). Replace each function body
# with a real Postgres/Chroma/CRM query when ready — the return shape is
# the contract, so the frontend never needs to change.


def get_revenue_report(tenant: dict, **kwargs) -> dict:
    """STILL A FIXTURE — no orders/invoices table exists in schema.sql,
    so there is no real revenue figure to query. Do not wire this to a
    Supabase query until that table is built; a query against
    nonexistent order data would just be a different way of making
    numbers up."""
    return {
        "spokenAnswer": (
            "Revenue is trending up eighteen percent week over week. "
            "Two accounts require your attention."
        ),
        "overlay": {
            "kind": "chart",
            "title": "Revenue · Last 7 Days",
            "chart": [
                {"label": "MON", "value": 42},
                {"label": "TUE", "value": 51},
                {"label": "WED", "value": 47},
                {"label": "THU", "value": 63},
                {"label": "FRI", "value": 71},
                {"label": "SAT", "value": 68},
                {"label": "SUN", "value": 84},
            ],
        },
    }


def get_runway_report(tenant: dict, **kwargs) -> dict:
    """STILL A FIXTURE — runway/burn/margin need real financial data
    (bank feed, accounting export, or at minimum an expenses table),
    none of which exists yet. See get_revenue_report's note."""
    return {
        "spokenAnswer": "Runway is healthy. Burn within tolerance across all subsystems.",
        "overlay": {
            "kind": "gauge",
            "title": "Runway & Burn",
            "gauges": [
                {"label": "RUNWAY", "value": 74, "max": 100, "unit": "%"},
                {"label": "BURN", "value": 42, "max": 100, "unit": "%"},
                {"label": "MARGIN", "value": 61, "max": 100, "unit": "%"},
                {"label": "CASH", "value": 88, "max": 100, "unit": "%"},
            ],
        },
    }


def get_pipeline_report(tenant: dict, **kwargs) -> dict:
    """STILL A FIXTURE — no deals/CRM table exists (tenant_tools has
    'crm.gohighlevel' as a switchbox row, but it's disabled and nothing
    reads from it yet). Wire this once the CRM tool is actually mounted
    and syncing real deal data. See get_revenue_report's note."""
    return {
        "spokenAnswer": "Displaying open pipeline. Two deals flagged urgent.",
        "overlay": {
            "kind": "table",
            "title": "Sales Pipeline",
            "table": {
                "columns": ["ID", "Account", "Owner", "Status"],
                "rows": [
                    {"status": "urgent", "cells": ["DL-412", "Northwind Corp", "Sales", "URGENT"]},
                    {"status": "urgent", "cells": ["DL-408", "Stark Industries", "Sales", "URGENT"]},
                    {"status": "pending", "cells": ["DL-402", "Wayne Ent.", "Sales", "PENDING"]},
                    {"status": "pending", "cells": ["DL-397", "Acme Robotics", "Sales", "PENDING"]},
                    {"status": "resolved", "cells": ["DL-388", "Initech LLC", "Sales", "CLOSED"]},
                ],
            },
        },
    }


def get_briefing_report(tenant: dict, **kwargs) -> dict:
    """Third real-data founder tool — synthesizes a briefing from what
    Jarvis actually has on hand: message volume, new customers,
    toleration timeouts, and catalog stock alerts, all scoped to this
    tenant. No fabricated numbers.

    There is deliberately no revenue/runway/pipeline data here — those
    would need an orders/deals/CRM table that doesn't exist anywhere in
    schema.sql yet (this tenant is a wholesale supplier with no
    structured order data today). get_revenue_report, get_runway_report,
    and get_pipeline_report stay fixtures below until that data source
    is actually built — wiring them to "real" queries against tables
    that don't exist would just be fabricating numbers a different way.
    """
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    lines: list[str] = []

    try:
        msg_count = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("tenant_id", tenant["id"])
            .gte("created_at", since_24h)
            .execute()
        ).count or 0
        lines.append(f"{msg_count} message{'s' if msg_count != 1 else ''} exchanged in the last 24 hours.")
    except Exception as err:
        print(f"get_briefing_report messages query failed: {err}")

    try:
        new_user_count = (
            supabase.table("users")
            .select("id", count="exact")
            .eq("tenant_id", tenant["id"])
            .gte("created_at", since_24h)
            .execute()
        ).count or 0
        if new_user_count:
            lines.append(
                f"{new_user_count} new customer{'s' if new_user_count != 1 else ''} reached out for the first time."
            )
    except Exception as err:
        print(f"get_briefing_report users query failed: {err}")

    try:
        tenant_user_ids = [
            r["id"]
            for r in supabase.table("users").select("id").eq("tenant_id", tenant["id"]).execute().data
        ]
        if tenant_user_ids:
            flagged_count = (
                supabase.table("moderation_state")
                .select("user_id", count="exact")
                .in_("user_id", tenant_user_ids)
                .gte("hard_ignore_until", datetime.now(timezone.utc).isoformat())
                .execute()
            ).count or 0
            if flagged_count:
                lines.append(
                    f"{flagged_count} user{'s' if flagged_count != 1 else ''} currently in a toleration timeout."
                )
    except Exception as err:
        print(f"get_briefing_report moderation query failed: {err}")

    try:
        collection = _get_catalog(tenant["chroma_collection"])
        sample = collection.get(limit=200, include=["metadatas"])
        metadatas = sample.get("metadatas") or []
        out_ids = [m.get("product_id", "?") for m in metadatas if m.get("stock_status") == "out_of_stock"]
        low_ids = [m.get("product_id", "?") for m in metadatas if m.get("stock_status") == "low_stock"]
        if out_ids:
            lines.append(f"Out of stock: {', '.join(out_ids)}.")
        if low_ids:
            lines.append(f"Running low: {', '.join(low_ids)}.")
    except Exception as err:
        print(f"get_briefing_report catalog scan failed: {err}")

    if not lines:
        lines = ["No notable activity in the last 24 hours."]

    return {
        "spokenAnswer": " ".join(lines[:2]),
        "overlay": {
            "kind": "report",
            "title": "Morning Briefing",
            "report": lines,
        },
    }


def _usage_report_data(tenant: dict) -> dict:
    """Raw data fetch only — no English generated here. Kept separate
    from get_usage_report() for two reasons: (1) the eval engine
    (eval_usage_grounding.py) needs to compute the SAME ground truth
    the production code used, without spinning up an LLM call to get
    it; (2) it's the one place the actual numbers get produced, so
    there's exactly one query to audit if a number is ever wrong.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = (
        supabase.table("usage_events")
        .select("created_at")
        .eq("tenant_id", tenant["id"])
        .gte("created_at", since)
        .execute()
    ).data

    counts_by_date: dict[str, int] = {}
    for r in rows:
        day = r["created_at"][:10]  # YYYY-MM-DD
        counts_by_date[day] = counts_by_date.get(day, 0) + 1

    today = datetime.now(timezone.utc).date()
    chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart.append({"label": d.strftime("%a").upper(), "value": counts_by_date.get(d.isoformat(), 0)})

    return {"total_calls": sum(c["value"] for c in chart), "chart": chart}


async def _synthesize_grounded_answer(user_text: str, data_summary: str, tenant: dict) -> str:
    """The actual anti-hallucination step. The model is handed ONLY the
    founder's question and the real numbers just pulled from the
    database — never the freedom to explain how it computed them, only
    to phrase what's already there. It cannot invent a number that
    isn't in data_summary without ignoring an explicit instruction not
    to, which is exactly what eval_usage_grounding.py checks for.

    This mirrors main.py's ask_llm() catalog-grounding pattern
    ("Answer ONLY using the catalog information below") — same
    technique, applied to structured founder data instead of RAG text.

    Runs through llm_router.route() (Groq/Gemini fallback chain), not a
    direct Ollama call — RunPod (the previous backing GPU) was abandoned
    per PROGRESS.md 2026-07-13; this matches main.py's ask_llm(), which
    made the same migration for the Telegram path.
    """
    system_prompt = (
        "You are Jarvis, a founder's assistant. Below is REAL data just "
        "retrieved from the business's own database. Answer the "
        "founder's question in ONE short spoken sentence, using ONLY "
        "the numbers and facts given below. Never invent, estimate, or "
        "round differently than what's given. If the data doesn't "
        "actually answer the question, say so plainly instead of "
        "guessing.\n\n"
        f"REAL DATA:\n{data_summary}"
    )
    prompt = f"{system_prompt}\n\nFounder: {user_text or 'How are we doing?'}\nJarvis:"
    try:
        text = await asyncio.to_thread(
            llm_router.route,
            task_type="agent_turn",
            prompt=prompt,
            tenant_tier=tenant.get("tier", "basic"),
            providers=_TEXT_PROVIDERS,
            usage_logger=_usage_logger_for(tenant),
        )
        return text.strip() or data_summary
    except Exception as err:
        print(f"_synthesize_grounded_answer failed: {err}")
        return data_summary  # fail toward showing the real numbers, never silence


def _usage_data_summary(data: dict) -> str:
    """The exact text handed to the LLM as 'real data' — factored out so
    eval_usage_grounding.py can extract numbers from precisely what the
    model was shown (including the '7' in 'last 7 days'), not just the
    chart values. Otherwise the eval would flag a correctly-grounded
    answer as hallucinating just for repeating the time window back."""
    return (
        f"Total LLM calls in the last 7 days: {data['total_calls']}. "
        "Daily breakdown: "
        + ", ".join(f"{c['label']}={c['value']}" for c in data["chart"])
        + "."
    )


async def get_usage_report(tenant: dict, user_text: str = "", **kwargs) -> dict:
    """First real-data founder tool — everything else here is still a
    Phase 0 fixture. Pulls actual usage_events rows for the last 7 days,
    buckets them by day, then hands those real numbers to the LLM to
    phrase as a spoken answer (see _synthesize_grounded_answer). No new
    schema needed; usage_events already exists and has been logging
    since the Telegram path went live.
    """
    try:
        data = _usage_report_data(tenant)
    except Exception as err:
        print(f"get_usage_report query failed: {err}")
        return {
            "spokenAnswer": "I couldn't reach the database just now. Try again in a moment.",
            "overlay": None,
        }

    data_summary = _usage_data_summary(data)
    spoken = await _synthesize_grounded_answer(user_text, data_summary, tenant)

    return {
        "spokenAnswer": spoken,
        "overlay": {
            "kind": "chart",
            "title": "LLM Calls · Last 7 Days",
            "chart": data["chart"],
        },
    }



def get_catalog_report(tenant: dict, query: str = "", **kwargs) -> dict:
    """Second real-data founder tool — searches the tenant's Chroma
    catalog collection (see ingest.py / main.py's RAG path).

    Exact-match first: product codes like 'KP005' are meaningless tokens
    to the embedding model (observed live 2026-07-14: a kp005 query
    retrieved KP001/KP012/KP003/KP008 but not KP005 on the Telegram
    path — same weakness here). Any code-shaped token in the query gets a
    direct metadata lookup; semantic search covers everything else. With
    no query at all, falls back to a generic sample (.get()).
    """
    try:
        collection = _get_catalog(tenant["chroma_collection"])
        metadatas = []
        if query.strip():
            seen_ids: set[str] = set()
            for code in re.findall(r"\b([A-Za-z]{1,4}\d{2,5})\b", query):
                exact = collection.get(
                    where={"product_id": code.upper()}, include=["metadatas"]
                )
                for m in exact.get("metadatas") or []:
                    pid = m.get("product_id")
                    if pid not in seen_ids:
                        metadatas.append(m)
                        seen_ids.add(pid)
            if not metadatas:  # no code hit — plain semantic search
                result = collection.query(
                    query_texts=[query], n_results=8, include=["metadatas"]
                )
                metadatas = result.get("metadatas", [[]])[0]
        else:
            result = collection.get(limit=8, include=["metadatas"])
            metadatas = result.get("metadatas") or []
    except Exception as err:
        print(f"get_catalog_report query failed: {err}")
        return {
            "spokenAnswer": "I couldn't reach the product catalog just now.",
            "overlay": None,
        }

    if not metadatas:
        return {
            "spokenAnswer": (
                f"Nothing in the catalog matched '{query}'."
                if query.strip()
                else "The catalog looks empty — nothing has been ingested yet."
            ),
            "overlay": None,
        }

    rows = []
    for m in metadatas:
        stock_status = m.get("stock_status", "unknown")
        status = "resolved" if stock_status == "in_stock" else (
            "urgent" if stock_status == "out_of_stock" else "pending"
        )
        rows.append(
            {
                "status": status,
                "cells": [
                    m.get("product_id", "—"),
                    m.get("category", "—"),
                    stock_status.replace("_", " "),
                ],
            }
        )

    spoken = (
        f"Showing {len(rows)} products matching '{query}'."
        if query.strip()
        else f"Showing {len(rows)} products from the catalog."
    )

    return {
        "spokenAnswer": spoken,
        "overlay": {
            "kind": "table",
            "title": f"Product Catalog{f' · {query}' if query.strip() else ''}",
            "table": {
                "columns": ["Product ID", "Category", "Stock Status"],
                "rows": rows,
            },
        },
    }


FOUNDER_TOOLS = {
    "get_revenue_report": get_revenue_report,
    "get_runway_report": get_runway_report,
    "get_pipeline_report": get_pipeline_report,
    "get_briefing_report": get_briefing_report,
    "get_usage_report": get_usage_report,
    "get_catalog_report": get_catalog_report,
}

# JSON-schema tool definitions handed to the model — this is what lets it
# reason about meaning ("how are we doing on sales?") instead of requiring
# an exact keyword match.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_revenue_report",
            "description": (
                "Get the founder's revenue trend for the last 7 days, "
                "including any accounts that need attention."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_runway_report",
            "description": "Get the company's cash runway, burn rate, and margin health.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_report",
            "description": (
                "Get the open sales pipeline, including deals flagged "
                "urgent or pending."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_briefing_report",
            "description": "Get a compiled morning briefing of overnight and daily highlights.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_usage_report",
            "description": (
                "Get real system usage: how many AI/LLM calls have been "
                "made in the last 7 days, day by day."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_catalog_report",
            "description": (
                "Search the product catalog — what items exist, their "
                "category, and stock status. Use for questions about "
                "products, inventory, or what's in stock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "REQUIRED whenever the founder mentions any "
                            "specific product, product ID/code (e.g. "
                            "'KP005', 'kp001'), material, size, or "
                            "category — extract that exact term as the "
                            "query (e.g. 'kp005', 'GI pipes', 'copper "
                            "fittings'). Only send an empty string when "
                            "the founder asks for a general overview of "
                            "the whole catalog with no specific item "
                            "mentioned."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def _normalize_message(provider: str, raw: dict) -> dict:
    """Groq (OpenAI-compatible) and Ollama return differently-shaped
    responses for the same concept. This is the one place that
    difference gets flattened, so everything downstream just deals
    with a single {"content": ..., "tool_calls": [...]} shape."""
    if provider == "groq":
        return raw["choices"][0]["message"]
    return raw.get("message", {})  # ollama's native shape


def _parse_tool_args(raw_args) -> dict:
    """Groq (OpenAI format) sends tool arguments as a JSON-encoded
    string; Ollama sends them as an already-parsed dict. Handle both
    rather than assuming one."""
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return raw_args or {}


async def _call_tool_model(messages: list, tools: list | None = None) -> dict:
    """Walks TOOL_CALL_CHAIN, returning the first successful provider's
    normalized message. This is the tool-deciding call's fallback chain
    — separate from llm_router.route() because that only returns flat
    text, and this needs real structured tool_calls back."""
    last_err = None
    for provider_name, model in TOOL_CALL_CHAIN:
        try:
            raw = await asyncio.to_thread(
                providers.get_raw_chat_call(provider_name, model), messages, tools, 20
            )
            return _normalize_message(provider_name, raw)
        except Exception as err:
            print(f"founder tool-call provider {provider_name}/{model} failed: {err}")
            last_err = err
            continue
    raise RuntimeError(f"All tool-call providers failed; last error: {last_err}")


TOOL_SYSTEM_PROMPT = (
    "You are Jarvis, an assistant for a startup founder. You have a "
    "small set of tools that pull real business data: revenue, runway, "
    "pipeline, a morning briefing, usage stats, and the product catalog. "
    "If the founder's question clearly matches one of these, call that "
    "tool. Questions about the company's own background — its address, "
    "hours, brands, history, contact details — have NO tool; do not call "
    "one for those. If it's a general, personal, or conversational "
    "question that no tool covers, do NOT call a tool — just don't call "
    "anything, and a different model will handle the reply."
)

CHAT_SYSTEM_PROMPT = (
    "You are the founder's personal assistant inside Jarvis Core. Answer "
    "directly and conversationally — this response will be spoken aloud, "
    "so keep it brief and natural, not a bulleted list."
)


def _chat_system_prompt(tenant: dict) -> str:
    """Tenant-aware version of CHAT_SYSTEM_PROMPT for the no-tool
    conversational fallback. Appends the tenant's company profile (loaded
    into the tenants row by load_company_profile.py) so voice questions
    like 'what's our address' or 'which brands do we carry' get grounded
    answers instead of a generic-model guess. Falls back to the bare
    constant when no profile is configured — behavior identical to
    pre-2026-07-15 in that case."""
    profile = (tenant.get("company_profile") or "").strip()
    if not profile:
        return CHAT_SYSTEM_PROMPT
    return (
        CHAT_SYSTEM_PROMPT
        + "\n\nWhen the founder asks about the company itself, answer from "
        "this profile and nothing else — never invent company facts:\n\n"
        f"COMPANY PROFILE:\n{profile}"
    )


async def invoke_tool(tool, tenant: dict, user_text: str = "", **args) -> dict:
    """Dispatches to a FOUNDER_TOOLS entry regardless of whether it's a
    plain sync fixture (get_revenue_report etc.) or an async, LLM-
    grounded real-data tool (get_usage_report). Every tool receives the
    founder's original question as user_text so a grounded tool can
    phrase its answer around what was actually asked, not just dump a
    fixed template. Takes the full tenant dict (id, chroma_collection,
    tier, ...) rather than a bare tenant_id, so per-tenant Chroma lookups
    (get_catalog_report, get_briefing_report's stock scan) work without
    each tool re-resolving the tenant itself."""
    if asyncio.iscoroutinefunction(tool):
        return await tool(tenant, user_text=user_text, **args)
    return tool(tenant, user_text=user_text, **args)


async def route_founder_query(text: str, tenant: dict) -> dict:
    """Two-tier model routing:
      1. The tool-calling chain (TOOL_CALL_CHAIN, currently Groq) decides
         whether a founder tool answers this question, and calls it if so.
      2. If no tool fires, hand off to a plain conversational call via
         llm_router.route() (no tools attached) for a real answer.
         Models tend to force a tool call when tools are present even
         when nothing fits, which is why general/personal questions
         came back wrong or empty before this split.

    Both steps now go through cloud fallback chains (Groq/Gemini) rather
    than a direct call to RunPod's Ollama instance — that pod
    (xl0rixu7dkzh1b) was abandoned per PROGRESS.md 2026-07-13, the exact
    same production-reliability fix main.py's ask_llm() already got.
    """
    try:
        message = await _call_tool_model(
            messages=[
                {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            tools=TOOLS,
        )
    except Exception as err:  # every provider in the chain failed
        print(f"Founder routing LLM call failed: {err}")
        return {
            "spokenAnswer": "I couldn't reach the reasoning engine just now. Try again in a moment.",
            "overlay": None,
        }

    tool_calls = message.get("tool_calls") or []

    if tool_calls:
        call = tool_calls[0]["function"]
        name = call.get("name")
        args = _parse_tool_args(call.get("arguments"))

        print(f"DEBUG tool call: name={name!r} args={args!r}")

        tool = FOUNDER_TOOLS.get(name)
        if tool:
            return await invoke_tool(tool, tenant, user_text=text, **args)

    # No tool matched — general/personal question. Hand off to the
    # conversational model instead of trusting the tool-deciding model's
    # own (tool-biased) reply, which is often empty or oddly terse when
    # tools are attached.
    try:
        prompt = f"{_chat_system_prompt(tenant)}\n\nFounder: {text}\nJarvis:"
        spoken = await asyncio.to_thread(
            llm_router.route,
            task_type="agent_turn",
            prompt=prompt,
            tenant_tier=tenant.get("tier", "basic"),
            providers=_TEXT_PROVIDERS,
            usage_logger=_usage_logger_for(tenant),
        )
        spoken = spoken.strip()
    except Exception as err:
        print(f"Conversational fallback call failed: {err}")
        spoken = ""

    return {
        "spokenAnswer": spoken
        or "I'm having trouble answering that right now — try again in a moment.",
        "overlay": None,
    }


@router.websocket("/ws/founder/{tenant_slug}")
async def founder_socket(websocket: WebSocket, tenant_slug: str):
    """One persistent connection per founder chat session.

    tenant_slug was already part of the URL — the frontend has been
    sending it since this route was written — but the handler threw it
    away and hardcoded tenant_id = 1 underneath. Now it's actually used:
    a bad/unknown slug gets a clean close instead of silently answering
    with tenant #1's data.
    """
    try:
        tenant = resolve_tenant(tenant_slug)
    except UnknownTenant:
        await websocket.close(code=4404, reason=f"Unknown tenant: {tenant_slug}")
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") != "query":
                continue

            text = msg.get("text", "")

            await websocket.send_json({"type": "status", "content": "thinking"})
            result = await route_founder_query(text, tenant)
            await websocket.send_json(
                {
                    "type": "response",
                    "spokenAnswer": result["spokenAnswer"],
                    "overlay": result["overlay"],
                }
            )
    except WebSocketDisconnect:
        pass
