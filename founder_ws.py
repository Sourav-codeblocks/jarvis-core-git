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
from datetime import datetime, timedelta, timezone

import chromadb
import httpx
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from supabase import create_client

load_dotenv()  # self-sufficient — don't depend on main.py's import order

router = APIRouter()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

_chroma = chromadb.PersistentClient(path="chroma_db")
_catalog_collection = None


def _get_catalog():
    """Lazy-loaded so importing this module doesn't blow up if chroma_db
    or the collection isn't there yet. Same collection ingest.py
    populates and main.py's RAG path already queries.

    NOTE: main.py hardcodes "kb_keshri_pipes" (the spelling actually used
    on disk, per PROGRESS.md); schema.sql's seed row uses
    "kb_kesari_pipes" instead — the same discrepancy code_review.md
    already flagged. Using the disk spelling here to match what's
    actually populated.
    """
    global _catalog_collection
    if _catalog_collection is None:
        _catalog_collection = _chroma.get_collection(
            name="kb_keshri_pipes",
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )
    return _catalog_collection


OLLAMA_URL = f"{os.environ.get('OLLAMA_URL', 'http://localhost:11434')}/api/chat"
AGENT_MODEL = "qwen2.5:7b-instruct-q8_0"  # same tag as llm_router.py's agent_turn local model
CHAT_MODEL = "mistral:7b-instruct-q8_0"  # plain conversation, no tools — already pulled per ollama list

# --- Founder tool registry -------------------------------------------------
# Phase 0 stand-ins with the exact payload shape the frontend already
# expects (see dataAdapter.ts OverlayPayload). Replace each function body
# with a real Postgres/Chroma/CRM query when ready — the return shape is
# the contract, so the frontend never needs to change.


def get_revenue_report(tenant_id: int, **kwargs) -> dict:
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


def get_runway_report(tenant_id: int, **kwargs) -> dict:
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


def get_pipeline_report(tenant_id: int, **kwargs) -> dict:
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


def get_briefing_report(tenant_id: int, **kwargs) -> dict:
    return {
        "spokenAnswer": "Compiled briefing ready. Highlights on screen.",
        "overlay": {
            "kind": "report",
            "title": "Morning Briefing",
            "report": [
                "// 06:00 — Uplink stable across all regions.",
                "// 06:14 — Overnight batch jobs completed without incident.",
                "// 07:02 — Two new leads inbound from EMEA channel.",
                "// 07:41 — Reminder: board sync at 15:00 local.",
                "// 08:00 — Recommend reviewing DL-412 before standup.",
            ],
        },
    }


def get_usage_report(tenant_id: int, **kwargs) -> dict:
    """First real-data founder tool — everything else here is still a
    Phase 0 fixture. Pulls actual usage_events rows for the last 7 days
    and buckets them by day. No new schema needed; usage_events already
    exists and has been logging since the Telegram path went live."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    try:
        rows = (
            supabase.table("usage_events")
            .select("created_at")
            .eq("tenant_id", tenant_id)
            .gte("created_at", since)
            .execute()
        ).data
    except Exception as err:
        print(f"get_usage_report query failed: {err}")
        return {
            "spokenAnswer": "I couldn't reach the database just now. Try again in a moment.",
            "overlay": None,
        }

    counts_by_date: dict[str, int] = {}
    for r in rows:
        day = r["created_at"][:10]  # YYYY-MM-DD
        counts_by_date[day] = counts_by_date.get(day, 0) + 1

    today = datetime.now(timezone.utc).date()
    chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        chart.append({"label": d.strftime("%a").upper(), "value": counts_by_date.get(d.isoformat(), 0)})

    total_calls = sum(c["value"] for c in chart)
    spoken = (
        f"You've made {total_calls} LLM calls in the last 7 days."
        if total_calls
        else "No LLM usage recorded in the last 7 days yet."
    )

    return {
        "spokenAnswer": spoken,
        "overlay": {
            "kind": "chart",
            "title": "LLM Calls · Last 7 Days",
            "chart": chart,
        },
    }


def get_catalog_report(tenant_id: int, query: str = "", **kwargs) -> dict:
    """Second real-data founder tool — searches the tenant's Chroma
    catalog collection (see ingest.py / main.py's RAG path). If the model
    extracted a specific product/category from the question, this runs a
    real similarity search against it; with no query, falls back to a
    generic sample (.get()) since there's nothing to match against.
    """
    try:
        collection = _get_catalog()
        if query.strip():
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
                            "The specific product, material, or category "
                            "the founder is asking about, if any (e.g. "
                            "'GI pipes', 'copper fittings'). Leave empty "
                            "to show a general sample of the catalog."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
]


TOOL_SYSTEM_PROMPT = (
    "You are Jarvis, an assistant for a startup founder. You have a "
    "small set of tools that pull real business data: revenue, runway, "
    "pipeline, a morning briefing, usage stats, and the product catalog. "
    "If the founder's question clearly matches one of these, call that "
    "tool. If it's a general, personal, or conversational question that "
    "no tool covers, do NOT call a tool — just don't call anything, and "
    "a different model will handle the reply."
)

CHAT_SYSTEM_PROMPT = (
    "You are the founder's personal assistant inside Jarvis Core. Answer "
    "directly and conversationally — this response will be spoken aloud, "
    "so keep it brief and natural, not a bulleted list."
)


async def _call_ollama(
    model: str, system_prompt: str, text: str, tools: list | None = None
) -> dict:
    """Shared low-level Ollama call, used by both the tool-deciding model
    (qwen2.5) and the plain-conversation fallback model (llama3.1:8b)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()
        return resp.json()


async def route_founder_query(text: str, tenant_id: int) -> dict:
    """Two-tier model routing:
      1. qwen2.5 (tool schemas attached) decides whether a founder tool
         answers this question, and calls it if so.
      2. If no tool fires, hand off to llama3.1:8b — a plain
         conversational model with no tools attached — for a real
         answer. Models tend to force a tool call when tools are
         present even when nothing fits, which is why general/personal
         questions came back wrong or empty before this split.
    """
    try:
        data = await _call_ollama(AGENT_MODEL, TOOL_SYSTEM_PROMPT, text, tools=TOOLS)
    except Exception as err:  # Ollama down, model not pulled, timeout, etc.
        print(f"Founder routing LLM call failed: {err}")
        return {
            "spokenAnswer": "I couldn't reach the reasoning engine just now. Try again in a moment.",
            "overlay": None,
        }

    message = data.get("message", {})
    tool_calls = message.get("tool_calls") or []

    if tool_calls:
        call = tool_calls[0]["function"]
        name = call.get("name")
        args = call.get("arguments") or {}
        tool = FOUNDER_TOOLS.get(name)
        if tool:
            return tool(tenant_id, **args)

    # No tool matched — general/personal question. Hand off to the
    # conversational model instead of trusting qwen's own (tool-biased)
    # reply, which is often empty or oddly terse when tools are attached.
    try:
        chat_data = await _call_ollama(CHAT_MODEL, CHAT_SYSTEM_PROMPT, text)
        spoken = (chat_data.get("message", {}).get("content") or "").strip()
    except Exception as err:
        print(f"Conversational fallback (llama3.1:8b) call failed: {err}")
        spoken = ""

    return {
        "spokenAnswer": spoken
        or "I'm having trouble answering that right now — try again in a moment.",
        "overlay": None,
    }


@router.websocket("/ws/founder/{tenant_slug}")
async def founder_socket(websocket: WebSocket, tenant_slug: str):
    """One persistent connection per founder chat session.

    Phase 0: tenant_id hardcoded to 1 — same seam as the Telegram webhook
    in main.py.
    """
    await websocket.accept()
    tenant_id = 1

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
            result = await route_founder_query(text, tenant_id)
            await websocket.send_json(
                {
                    "type": "response",
                    "spokenAnswer": result["spokenAnswer"],
                    "overlay": result["overlay"],
                }
            )
    except WebSocketDisconnect:
        pass
