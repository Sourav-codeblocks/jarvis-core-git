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


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    print("INCOMING UPDATE:", update)  # dev visibility: watch messages arrive

    message = update.get("message")
    if not message or "text" not in message:
        return {"ok": True}  # ignore non-text updates (stickers, joins, etc.)

    chat_id = message["chat"]["id"]
    text = message["text"]

    # Phase 0 echo: prove the full loop works before adding the brain.
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": f"Jarvis Core received: {text}"},
        )

    return {"ok": True}