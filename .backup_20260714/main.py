"""Jarvis Core — Gateway (Phase 0).

The single entry point. Everything inbound (Telegram now, WhatsApp later)
passes through here: identify tenant -> identify user -> toleration check
-> hand to the tenant's agent -> reply back out.
"""


import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import founder_reports
from db_client import get_supabase, resolve_tenant, UnknownTenant
from founder_ws import router as founder_router
from voice_bridge import router as voice_router
from tts import router as tts_router

load_dotenv()  # pulls SUPABASE_URL, SUPABASE_SECRET_KEY, etc. from .env

app = FastAPI(title="Jarvis Core Gateway")

supabase = get_supabase()  # shared client — same instance db_client hands to every other module

# Phase 0: this gateway process still serves one Telegram bot token, so it
# still serves one tenant per deploy — but which tenant is now a config
# value, not a literal buried in the webhook handler. Adding tenant #2's
# own bot means a second deploy with its own TENANT_SLUG / bot token, not
# a code change here.
TENANT_SLUG = os.environ.get("TENANT_SLUG", "keshri-pipes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FOUNDER_UI_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
FOUNDER_API_KEY = os.environ["FOUNDER_API_KEY"]

def _check_founder_key(request: Request):
    if request.headers.get("x-founder-key") != FOUNDER_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/founder/reports")
def founder_reports_list(request: Request):
    _check_founder_key(request)
    return founder_reports.get_all_reports(supabase)

@app.get("/api/founder/reports/{report_id}")
def founder_report_detail(report_id: str, request: Request):
    _check_founder_key(request)
    report = founder_reports.get_report(supabase, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Unknown report")
    return report

@app.post("/api/founder/query")
async def founder_query(request: Request):
    _check_founder_key(request)
    body = await request.json()
    report_id = founder_reports.route_query(body.get("query", ""))
    report = founder_reports.get_report(supabase, report_id)
    return {"spokenAnswer": report["spokenAnswer"], "overlay": report["overlay"]}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(founder_router)
app.include_router(voice_router)
app.include_router(tts_router)

import llm_router
from providers import get_provider_call

# route() calls providers[name](model=, prompt=, timeout=); get_provider_call
# returns a closure that already has `model` bound and only takes
# (prompt, timeout). This shim bridges the two calling conventions without
# changing either llm_router.py or providers.py.
def _provider_shim(provider_name: str):
    def call(model: str, prompt: str, timeout: int):
        return get_provider_call(provider_name, model)(prompt, timeout)
    return call

CLOUD_PROVIDERS = {name: _provider_shim(name) for name in ("groq", "gemini")}

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

chroma = chromadb.PersistentClient(path="chroma_db")
_catalog_collections: dict[str, "chromadb.Collection"] = {}


def get_catalog_collection(collection_name: str):
    """Per-tenant Chroma collection, resolved by name and cached.

    Previously this was a single module-level `catalog` hardcoded to
    "kb_keshri_pipes" — fine for one tenant, but it meant every tenant's
    RAG queries would have silently hit tenant #1's catalog. Now the
    caller passes the tenant's own `chroma_collection` value (from the
    `tenants` table), so the One Rule holds for knowledge too, not just
    for id columns.

    NOTE: schema.sql's seed row still says "kb_kesari_pipes" while the
    collection actually populated on disk (per PROGRESS.md / ingest.py
    runs) is "kb_keshri_pipes" — the spelling mismatch code_review.md
    already flagged (build-queue item 5). That's a data-fix, not a
    tenant-resolution bug, so it's left alone here; align the DB row's
    chroma_collection value to the real on-disk collection name before
    relying on this in production.
    """
    if collection_name not in _catalog_collections:
        _catalog_collections[collection_name] = chroma.get_collection(
            name=collection_name,
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
        )
    return _catalog_collections[collection_name]

@app.get("/health")
def health():
    """Heartbeat: proves the gateway is alive AND can reach the database."""
    result = supabase.table("tenants").select("slug, display_name").execute()
    return {
        "gateway": "alive",
        "database": "connected",
        "tenants": result.data,
    }

# ---------------------------------------------------------------
# Telegram webhook — the first door on the gatehouse.
# Telegram POSTs every message here as JSON ("Update" object).
# Phase 0 step 1: receive, log, acknowledge. Brain comes next.
# ---------------------------------------------------------------

import httpx
from fastapi import Request

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def get_or_create_user(tenant_id: int, channel: str, channel_user_id: str,
                       display_name: str | None):
    """The gatehouse ledger: look up this visitor; register them if new.

    Every user belongs to a tenant — the One Rule (tenant_id flows through
    everything) starts enforcing itself right here.

    Takes an already-resolved tenant_id rather than a slug: the webhook
    resolves the slug once via db_client.resolve_tenant() and threads the
    same tenant_id through every downstream call (user lookup, message
    logging, usage logging) instead of each call re-resolving or, worse,
    each hardcoding its own literal.
    """
    existing = (
        supabase.table("users").select("*")
        .eq("tenant_id", tenant_id)
        .eq("channel", channel)
        .eq("channel_user_id", channel_user_id)
        .execute()
    )
    if existing.data:
        return existing.data[0], False  # known visitor

    created = (
        supabase.table("users").insert({
            "tenant_id": tenant_id,
            "channel": channel,
            "channel_user_id": channel_user_id,
            "display_name": display_name,
        }).execute()
    )
    return created.data[0], True  # newly registered


def get_recent_history(user_id: int, limit: int = 8) -> list[dict]:
    """Working memory: this user's last N messages, oldest first."""
    rows = (
        supabase.table("messages")
        .select("role, text")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [{"role": r["role"], "content": r["text"]} for r in reversed(rows.data)]

async def ask_llm(user_text: str, history: list[dict], tenant: dict) -> str:
    """First thought: one LLM call through the tunnel to dslab's Ollama.

    Phase 0: direct call with a minimal per-tenant persona built from the
    tenant's own display_name (was hardcoded to "Keshri Pipes" before).
    Next: this becomes a call into llm_router.route() with task_type routing,
    which will also make the persona/business_desc come from the tenant's
    config (see tenant.kesari.example.yaml's business_desc) rather than
    being reconstructed here.

    `tenant` is the dict resolve_tenant() returns — this is what makes RAG
    and usage logging land against the right tenant instead of tenant #1.
    """
    # RAG: retrieve the 4 most relevant catalog entries for this question,
    # from THIS tenant's own collection — not a hardcoded global one.
    catalog = get_catalog_collection(tenant["chroma_collection"])
    retrieved = catalog.query(query_texts=[user_text], n_results=4)
    catalog_context = "\n".join(retrieved["documents"][0])

    system_prompt = (
        f"You are the assistant for {tenant['display_name']}, a wholesale "
        "pipe fitting supplier. Be brief, warm, and professional. "
        "Hindi-English mix is fine if the customer uses it.\n\n"
        "Answer ONLY using the catalog information below. If the answer is "
        "not in the catalog, say you'll check with the team — never invent "
        "products, prices, or stock.\n\n"
        f"CATALOG:\n{catalog_context}"
    )
    # providers.py's call interface is a single flat prompt string (no
    # native system/history support yet) -- fold system + history + user
    # turn into one prompt. Revert this flattening once providers.py grows
    # proper message-list support; tracked alongside the RunPod->cloud swap.
    prompt = system_prompt + "\n\n"
    for turn in history:
        speaker = "Customer" if turn["role"] == "user" else "Assistant"
        prompt += f"{speaker}: {turn['content']}\n"
    prompt += f"Customer: {user_text}\nAssistant:"

    def usage_logger(task_type, model, provider, latency_ms, **usage):
        supabase.table("usage_events").insert({
            "tenant_id": tenant["id"],
            "task_type": task_type,
            "model": model,
            "provider": provider,
            "latency_ms": latency_ms,
            **usage,
        }).execute()

    return llm_router.route(
        task_type="agent_turn",
        prompt=prompt,
        tenant_tier=tenant["tier"],
        providers=CLOUD_PROVIDERS,
        usage_logger=usage_logger,
    )

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    print("INCOMING UPDATE:", update)  # dev visibility: watch messages arrive

    message = update.get("message")
    if not message or "text" not in message:
        return {"ok": True}  # ignore non-text updates (stickers, joins, etc.)

    chat_id = message["chat"]["id"]
    text = message["text"]

    try:
        tenant = resolve_tenant(TENANT_SLUG)
    except UnknownTenant as err:
        # Config problem (bad TENANT_SLUG), not a customer-facing failure —
        # log it and ack the webhook so Telegram doesn't retry-storm us.
        print(f"telegram_webhook: {err}")
        return {"ok": True}

    sender = message["from"]
    display_name = " ".join(
        filter(None, [sender.get("first_name"), sender.get("last_name")])
    )
    user, is_new = get_or_create_user(
        tenant_id=tenant["id"],               # resolved from TENANT_SLUG, not hardcoded.
        channel="telegram",                   # Later: resolved per-bot from DB.
        channel_user_id=str(sender["id"]),
        display_name=display_name,
    )
    print(f"USER: {user['display_name']} (id={user['id']}, "
          f"new={is_new}, reputation={user['reputation']})")

    # First thought: route the message through the LLM, reply with its answer.
    history = get_recent_history(user["id"])

    supabase.table("messages").insert({
        "tenant_id": tenant["id"], "user_id": user["id"], "role": "user", "text": text,
    }).execute()

    reply = await ask_llm(text, history, tenant)

    supabase.table("messages").insert({
        "tenant_id": tenant["id"], "user_id": user["id"], "role": "assistant", "text": reply,
    }).execute()

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
        )

    return {"ok": True}