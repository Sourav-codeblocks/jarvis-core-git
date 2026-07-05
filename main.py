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