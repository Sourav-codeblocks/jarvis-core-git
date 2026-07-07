"""Jarvis Core — Gateway (Phase 0).

The single entry point. Everything inbound (Telegram now, WhatsApp later)
passes through here: identify tenant -> identify user -> toleration check
-> hand to the tenant's agent -> reply back out.
"""


import os
from dotenv import load_dotenv
from fastapi import FastAPI
from supabase import create_client

load_dotenv()  # pulls SUPABASE_URL, SUPABASE_SECRET_KEY, etc. from .env

app = FastAPI(title="Jarvis Core Gateway")

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

chroma = chromadb.PersistentClient(path="chroma_db")
catalog = chroma.get_collection(
    name="kb_keshri_pipes",
    embedding_function=SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2"),
)

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

def get_or_create_user(tenant_slug: str, channel: str, channel_user_id: str,
                       display_name: str | None):
    """The gatehouse ledger: look up this visitor; register them if new.

    Every user belongs to a tenant — the One Rule (tenant_id flows through
    everything) starts enforcing itself right here.
    """
    tenant = (
        supabase.table("tenants").select("id").eq("slug", tenant_slug)
        .single().execute()
    )
    tenant_id = tenant.data["id"]

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

async def ask_llm(user_text: str, history: list[dict]) -> str:
    """First thought: one LLM call through the tunnel to dslab's Ollama.

    Phase 0: direct call with a minimal Keshri Pipes persona.
    Next: this becomes a call into llm_router.route() with task_type routing.
    """
    # RAG: retrieve the 4 most relevant catalog entries for this question.
    retrieved = catalog.query(query_texts=[user_text], n_results=4)
    catalog_context = "\n".join(retrieved["documents"][0])

    system_prompt = (
        "You are the assistant for Keshri Pipes, a wholesale pipe fitting "
        "supplier. Be brief, warm, and professional. Hindi-English mix is "
        "fine if the customer uses it.\n\n"
        "Answer ONLY using the catalog information below. If the answer is "
        "not in the catalog, say you'll check with the team — never invent "
        "products, prices, or stock.\n\n"
        f"CATALOG:\n{catalog_context}"
    )
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:3b-instruct-q8_0",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *history,
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        supabase.table("usage_events").insert({
            "tenant_id": 1,                      # Phase 0: hardcoded, same seam as tenant_slug
            "task_type": "agent_turn",
            "model": "llama3.2:3b-instruct-q8_0",
            "provider": "ollama_dslab",
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "cost_usd": 0,                       # local model = free
            "latency_ms": int(data.get("total_duration", 0) / 1_000_000),
        }).execute()
        return data["message"]["content"]

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    print("INCOMING UPDATE:", update)  # dev visibility: watch messages arrive

    message = update.get("message")
    if not message or "text" not in message:
        return {"ok": True}  # ignore non-text updates (stickers, joins, etc.)

    chat_id = message["chat"]["id"]
    text = message["text"]

    sender = message["from"]
    display_name = " ".join(
        filter(None, [sender.get("first_name"), sender.get("last_name")])
    )
    user, is_new = get_or_create_user(
        tenant_slug="keshri-pipes",          # Phase 0: one tenant, hardcoded.
        channel="telegram",                   # Later: resolved per-bot from DB.
        channel_user_id=str(sender["id"]),
        display_name=display_name,
    )
    print(f"USER: {user['display_name']} (id={user['id']}, "
          f"new={is_new}, reputation={user['reputation']})")

    # First thought: route the message through the LLM, reply with its answer.
    history = get_recent_history(user["id"])

    supabase.table("messages").insert({
        "tenant_id": 1, "user_id": user["id"], "role": "user", "text": text,
    }).execute()

    reply = await ask_llm(text, history)

    supabase.table("messages").insert({
        "tenant_id": 1, "user_id": user["id"], "role": "assistant", "text": reply,
    }).execute()

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
        )

    return {"ok": True}