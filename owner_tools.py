"""Jarvis Core — Owner-only tools (vendor forwarding, festival greetings).

Only reachable when the sender resolves to role='owner' on the users
table (see main.py's tool-calling gate). Customers and employees never
see these tools even exist — they're not in the tool list handed to the
model on their turns at all, not just prompted away from them.

Channel abstraction: send_channel_message() is the ONE place that knows
how to actually dispatch a message on a given channel. Telegram is real
today; WhatsApp is a clean, obvious stub. When WhatsApp support lands,
every tool in this file (and any future one) gets it for free — nothing
above this function needs to change.
"""

import os

import httpx
from db_client import get_supabase

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def resolve_identity_role(channel: str, channel_user_id: str) -> tuple[str | None, str | None]:
    """Looks up whether this channel account belongs to a known identity
    (admin/founder/staff) via channel_links -> identities. Returns
    (role, display_name), or (None, None) if this is just an ordinary
    customer — which is the overwhelmingly common case, so this should
    stay a cheap, single indexed lookup.

    This is deliberately SEPARATE from the users table (customer chat
    history, reputation) — identities is who's allowed to do owner-level
    things; users is who's talked to the bot. A person can be both (an
    owner is also logged in `users` from their very first message) but
    the two tables answer different questions and neither should be
    inferred from the other.
    """
    result = (
        get_supabase()
        .table("channel_links")
        .select("identity_id, identities(role, display_name, status)")
        .eq("channel", channel)
        .eq("channel_user_id", channel_user_id)
        .execute()
    )
    if not result.data:
        return None, None

    identity = result.data[0].get("identities")
    if not identity or identity.get("status") != "verified":
        # Row exists but revoked/pending — treat exactly like no identity
        # at all. A revoked admin must silently fall back to customer
        # behavior, never see an error that reveals they lost access.
        return None, None

    return identity["role"], identity.get("display_name")


async def send_channel_message(channel: str, channel_contact: str, text: str) -> bool:
    """Send a plain text message on the given channel. Returns True on
    confirmed delivery, False on any failure — callers must treat False
    as "did not send," never assume success.

    This function is the whole point: every tool that needs to actually
    message someone (a vendor, a customer, anyone) goes through here.
    Swapping Telegram for WhatsApp later means adding one real branch
    below — no other file changes.
    """
    if channel == "telegram":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={"chat_id": channel_contact, "text": text},
                )
                resp.raise_for_status()
                return True
        except Exception as err:
            print(f"send_channel_message (telegram) failed: {err}")
            return False

    if channel == "whatsapp":
        # Not implemented yet. Deliberately explicit rather than silently
        # pretending to succeed — a vendor row with channel='whatsapp'
        # today should fail loudly, not vanish a message.
        print(f"send_channel_message: WhatsApp not implemented yet (contact={channel_contact})")
        return False

    print(f"send_channel_message: unknown channel {channel!r}")
    return False


def find_vendor(tenant_id: int, category: str) -> dict | None:
    """Loose category match — vendor categories are free text (see
    owner_tools_schema.sql), so this does a case-insensitive substring
    match in both directions rather than requiring an exact string.
    Returns the first active match, or None."""
    rows = (
        get_supabase()
        .table("vendors")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .execute()
    ).data or []

    category_lower = category.lower().strip()
    for v in rows:
        v_cat = v["category"].lower().strip()
        if v_cat in category_lower or category_lower in v_cat:
            return v
    return None


async def forward_to_vendor(tenant: dict, requester_name: str, vendor_category: str,
                             product_details: str, customer_name: str = "",
                             customer_phone: str = "", notes: str = "", **kwargs) -> dict:
    """Forwards a real requirement to a real vendor. Returns a dict with
    a deterministic, factual `result_text` — the calling code (main.py)
    uses THIS text verbatim in the reply, rather than letting the model
    freely narrate what happened. This is the actual fix for last
    night's hallucinated-forward bug: success or failure is decided here,
    in code, from a real delivery result — never guessed by the LLM.
    """
    vendor = find_vendor(tenant["id"], vendor_category)

    if not vendor:
        return {
            "success": False,
            "result_text": (
                f"I couldn't find a vendor registered for '{vendor_category}' yet. "
                "No message was sent — you'll need to add that vendor first."
            ),
        }

    message_lines = [
        f"New requirement forwarded from {tenant['display_name']} ({requester_name}):",
        "",
        f"Details: {product_details}",
    ]
    if customer_name:
        message_lines.append(f"Customer: {customer_name}" + (f" ({customer_phone})" if customer_phone else ""))
    if notes:
        message_lines.append(f"Notes: {notes}")

    sent = await send_channel_message(vendor["channel"], vendor["channel_contact"], "\n".join(message_lines))

    if sent:
        return {
            "success": True,
            "result_text": f"Sent to {vendor['name']} on {vendor['channel']}. They'll have it now.",
        }
    return {
        "success": False,
        "result_text": (
            f"I tried to reach {vendor['name']} but the message didn't go through. "
            "Nothing was sent — worth trying again in a moment, or reaching them directly."
        ),
    }


# ─────────────────────────────────────────────────────────────────
# Tool-calling — same pattern founder_ws.py already proved out
# (Groq raw tool-calling), scoped to owner-only tools. Deliberately a
# SEPARATE, smaller tool set from founder_ws.py's FOUNDER_TOOLS — those
# are voice/typed-chat report tools; these are Telegram action tools.
# Kept apart so neither file has to reason about the other's tools.
# ─────────────────────────────────────────────────────────────────

import asyncio
import json

from providers import get_raw_chat_call

OWNER_TOOL_CHAIN = [("groq", "llama-3.3-70b-versatile")]

OWNER_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "forward_to_vendor",
            "description": (
                "Forward a customer or business requirement to a registered "
                "vendor (e.g. cement, steel, sanitaryware supplier). Only "
                "call this when the owner is CLEARLY asking to forward, "
                "send, or pass on a requirement to a specific vendor or "
                "category of vendor — not for ordinary catalog questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor_category": {"type": "string", "description": "e.g. 'cement', 'steel', 'pipes'"},
                    "product_details": {"type": "string", "description": "What's needed — item, quantity, specs"},
                    "customer_name": {"type": "string", "description": "Omit if not mentioned"},
                    "customer_phone": {"type": "string", "description": "Omit if not mentioned"},
                    "notes": {"type": "string", "description": "Delivery location/timing/other context, omit if none"},
                },
                "required": ["vendor_category", "product_details"],
            },
        },
    },
]

OWNER_TOOL_SYSTEM_PROMPT = (
    "You are helping the owner of this business manage requests. You have "
    "one tool available: forwarding a requirement to a vendor. Only call "
    "it when they clearly mean 'forward/send/pass this to X' — for "
    "anything else (catalog questions, casual conversation, anything you "
    "don't have a tool for), do NOT call a tool; a different response "
    "path handles that."
)


def _parse_tool_args(raw_args) -> dict:
    """Same defensive shape as founder_ws.py's version — Groq sends JSON
    string arguments, and a bare 'null' must never crash a **kwargs call."""
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return raw_args or {}


async def decide_and_run_owner_tool(text: str, tenant: dict, requester_name: str) -> dict | None:
    """Returns {"result_text": ..., "success": ...} if a tool fired,
    or None if nothing matched (caller should fall through to the normal
    conversational reply). Never raises — any provider failure here is
    logged and treated as "no tool matched," never a hard error the
    owner sees."""
    try:
        raw = await asyncio.to_thread(
            get_raw_chat_call(*OWNER_TOOL_CHAIN[0]),
            [
                {"role": "system", "content": OWNER_TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            OWNER_TOOLS_SCHEMA,
            20,
        )
        message = raw["choices"][0]["message"]
    except Exception as err:
        print(f"decide_and_run_owner_tool: tool-decision call failed (non-fatal): {err}")
        return None

    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None

    call = tool_calls[0]["function"]
    name = call.get("name")
    args = _parse_tool_args(call.get("arguments"))
    print(f"DEBUG owner tool call: name={name!r} args={args!r}")

    if name == "forward_to_vendor":
        return await forward_to_vendor(tenant, requester_name=requester_name, **args)

    return None
