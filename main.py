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

async def ask_llm(user_text: str, user_display_name: str) -> str:
    """First thought: one LLM call through the tunnel to dslab's Ollama.

    Phase 0: direct call with a minimal Keshri Pipes persona.
    Next: this becomes a call into llm_router.route() with task_type routing.
    """
    system_prompt = (
        "You are the assistant for Keshri Pipes, a wholesale pipe fitting "
        "supplier. Be brief, warm, and professional. Hindi-English mix is "
        "fine if the customer uses it. You help with products, orders, "
        "prices, and delivery questions."
    )
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:3b-instruct-q8_0",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

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
    reply = await ask_llm(text, user["display_name"])

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
        )

    return {"ok": True}