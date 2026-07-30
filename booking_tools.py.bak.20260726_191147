"""Jarvis Core — Booking tools (services/resources/bookings template).

Second vertical template, alongside owner_tools.py (action tools) and the
catalog/products template Keshri Pipes uses. Any future booking-style
tenant (dance academy, real estate visits, another salon) reuses this
file unchanged — only the tenant's own services/resources/schedule rows
differ.

Core rule enforced in CODE, not prompt: non-premium customers get a tool
with NO artist-choice parameter at all. The model can't offer a choice it
was never given the ability to make — same lesson as tonight's
false-action-confirmation bug: a hard constraint belongs in code, a
prompt instruction alone eventually gets talked around.

One Rule still applies: every function takes tenant_id and filters on it.
"""

import random
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

# TEMP, hardcoded (2026-07-26): the server's clock is UTC (confirmed via
# `timedatectl` — DigitalOcean's Bangalore REGION does not mean the OS
# clock is IST). Every real tenant today (Keshri Pipes, Mihika's Studio)
# is India-based, so this constant fixes a REAL, currently-active daily
# bug: for ~5.5 hours every day (after 6pm UTC), India has already
# flipped to the next calendar date while raw datetime.now() still
# thought it was the previous day — "today"/"tomorrow" would silently
# resolve wrong during that window.
#
# CORRECT LONG-TERM FIX, not built tonight: a per-tenant timezone column
# (e.g. tenants.timezone = 'Asia/Kolkata' vs 'Europe/Madrid' for a future
# Ibiza-based tenant), with every call site below taking tenant_id and
# looking up its real timezone instead of using this shared constant.
_DEFAULT_TZ = ZoneInfo("Asia/Kolkata")


def _local_now() -> datetime:
    return datetime.now(_DEFAULT_TZ)

from db_client import get_supabase
from owner_tools import send_channel_message  # reuse the SAME channel abstraction —
                                               # WhatsApp-readiness for artist notifications
                                               # comes free the moment that function supports it


# ── Premium gating ───────────────────────────────────────────────────────

def is_premium_customer(tenant_id: int, channel: str, channel_contact: str) -> bool:
    """Checked BEFORE deciding which tool schema the model even sees for
    this turn (see decide_and_run_booking_tool). Deliberately fails safe:
    any lookup error treats the customer as non-premium, never the
    reverse — a false negative just means no artist-choice perk; a false
    positive would let an unvetted customer pick artists, which is the
    actual thing this system exists to prevent."""
    try:
        result = (
            get_supabase()
            .table("premium_customers")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("channel", channel)
            .eq("channel_contact", channel_contact)
            .eq("is_active", True)
            .execute()
        )
        return bool(result.data)
    except Exception as err:
        print(f"is_premium_customer lookup failed (defaulting to non-premium): {err}")
        return False


# ── Availability ─────────────────────────────────────────────────────────

def _get_active_resources(tenant_id: int) -> list[dict]:
    return (
        get_supabase()
        .table("resources")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .execute()
    ).data or []


def _match_words(s: str) -> list[str]:
    """Lowercase, normalize common British/American spelling variants,
    split into words 3+ chars. Used for fuzzy service-name matching."""
    s = s.lower().replace("colour", "color")
    return [w for w in _re.findall(r"[a-z]+", s) if len(w) >= 3]


def _get_service(tenant_id: int, service_name_or_id) -> dict | None:
    q = get_supabase().table("services").select("*").eq("tenant_id", tenant_id).eq("is_active", True)
    if isinstance(service_name_or_id, int):
        return (q.eq("id", service_name_or_id).execute().data or [None])[0]

    rows = q.execute().data or []
    if not rows:
        return None

    # Word-overlap matching, not pure substring — catches spelling
    # variants ('hair colour' vs 'Hair Coloring') that a plain ilike
    # substring check misses entirely. Found live 2026-07-26: a real
    # customer's British spelling got a false "we don't have that"
    # for a service that clearly exists.
    query_words = _match_words(service_name_or_id)
    best, best_score = None, 0
    for row in rows:
        row_words = _match_words(row["name"])
        score = sum(1 for qw in query_words for rw in row_words if qw in rw or rw in qw)
        if score > best_score:
            best, best_score = row, score
    return best


def build_services_catalog_text(tenant_id: int) -> str:
    """Plain-text services listing, read directly from the `services`
    table — no ChromaDB involved. Booking-template tenants are small
    enough (a handful of services) that semantic vector search buys
    nothing; a direct SQL read is simpler and equally grounded. Called
    from main.py's ask_llm() instead of the Chroma catalog path whenever
    tenant_tools has booking.enabled=true for this tenant.

    Also includes any retail PRODUCTS this tenant sells (the `products`
    table Keshri Pipes-style catalog tenants use) — for a combined
    business that both sells products AND takes appointments (e.g. a
    beauty store with an attached salon), both need to show up in the
    same conversation, not just services."""
    rows = (
        get_supabase()
        .table("services")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .execute()
    ).data or []

    sections = []
    if rows:
        lines = []
        for s in rows:
            price = f"Rs {s['base_price']:.0f}" if s.get("base_price") is not None else "price on request"
            lines.append(f"{s['name']} — {s['duration_min']} min, {price}")
        sections.append("SERVICES (bookable appointments):\n" + "\n".join(lines))

    try:
        product_rows = (
            get_supabase()
            .table("products")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("is_active", True)
            .execute()
        ).data or []
    except Exception:
        product_rows = []  # tenant has no products table usage at all — fine, services-only

    if product_rows:
        lines = []
        for p in product_rows:
            price = f"Rs {p['price_inr_per_unit']:.0f}" if p.get("price_inr_per_unit") is not None else "price on request"
            stock = p.get("stock_status", "")
            lines.append(f"{p['name']} ({p.get('product_id', '')}) — {price}, {stock}".strip())
        sections.append("PRODUCTS (retail items):\n" + "\n".join(lines))

    if not sections:
        return "(no services or products configured yet)"
    return "\n\n".join(sections)


def _existing_bookings_for_resource(resource_id: int, day_start: datetime, day_end: datetime) -> list[dict]:
    return (
        get_supabase()
        .table("bookings")
        .select("start_time, end_time")
        .eq("resource_id", resource_id)
        .not_.in_("status", ["cancelled"])
        .gte("start_time", day_start.isoformat())
        .lt("start_time", day_end.isoformat())
        .execute()
    ).data or []


def get_available_slots(tenant_id: int, service_name: str, date_str: str,
                         slot_granularity_min: int = 30) -> list[dict]:
    """Returns a list of {resource_id, resource_name, start_time} candidate
    slots for the given service on the given date, across ALL active
    resources. Every existing booking of ANY source (chatbot, walk_in,
    artist_self, receptionist) is already in the `bookings` table this
    reads from — that shared table is the entire mechanism that keeps
    online and offline bookings from colliding.

    date_str: 'YYYY-MM-DD'. Timezone handling kept simple (naive, tenant's
    local time assumed) — fine for a single-city salon; would need real
    timezone awareness for a multi-region tenant.
    """
    service = _get_service(tenant_id, service_name)
    if not service:
        return []

    date = datetime.strptime(date_str, "%Y-%m-%d")
    day_of_week = (date.weekday() + 1) % 7  # Python: Mon=0..Sun=6 -> ours: Sun=0..Sat=6
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    duration = timedelta(minutes=service["duration_min"])

    slots = []
    for resource in _get_active_resources(tenant_id):
        schedule_rows = (
            get_supabase()
            .table("resource_schedules")
            .select("*")
            .eq("resource_id", resource["id"])
            .eq("day_of_week", day_of_week)
            .execute()
        ).data or []
        if not schedule_rows:
            continue  # this artist doesn't work this day of week

        existing = _existing_bookings_for_resource(resource["id"], day_start, day_end)
        break_delta = timedelta(minutes=resource["break_after_booking_min"])

        for sched in schedule_rows:
            work_start = datetime.combine(date, dtime.fromisoformat(sched["start_time"]))
            work_end = datetime.combine(date, dtime.fromisoformat(sched["end_time"]))

            cursor = work_start
            while cursor + duration <= work_end:
                candidate_end = cursor + duration
                conflict = False
                for b in existing:
                    b_start = datetime.fromisoformat(b["start_time"]).replace(tzinfo=None)
                    b_end = datetime.fromisoformat(b["end_time"]).replace(tzinfo=None) + break_delta
                    if cursor < b_end and candidate_end + break_delta > b_start:
                        conflict = True
                        break
                if not conflict:
                    slots.append({
                        "resource_id": resource["id"],
                        "resource_name": resource["name"],
                        "start_time": cursor.isoformat(),
                    })
                cursor += timedelta(minutes=slot_granularity_min)

    return slots


# ── Booking creation ──────────────────────────────────────────────────────

async def create_booking(tenant: dict, service_name: str, start_time_iso: str,
                          resource_id: int | None, user_id: int | None,
                          customer_name: str = "", **kwargs) -> dict:
    """Deterministic result, decided in code — same pattern as
    owner_tools.forward_to_vendor. The model reports exactly result_text,
    never improvises around it.

    resource_id: if None, one is chosen automatically from the available
    slots for this service/time (random.choice among valid candidates —
    this is the actual "auto-assign, no customer choice" enforcement for
    non-premium customers; premium customers' chosen resource_id is
    validated against real availability before being trusted, never
    taken on faith from the model).

    On success, notifies the assigned artist if they have a real
    channel_contact on file (NULL/empty until a real artist is seeded —
    see artist_receptionist_roles_migration.sql). A booking still succeeds
    even if that notification fails to send; the booking itself and the
    notification are two separate concerns, and a Telegram hiccup should
    never un-book someone."""
    service = _get_service(tenant["id"], service_name)
    if not service:
        return {"success": False, "result_text": f"I couldn't find a service called '{service_name}'."}

    date_str = start_time_iso[:10]
    slots = get_available_slots(tenant["id"], service_name, date_str)
    matching = [s for s in slots if s["start_time"][:16] == start_time_iso[:16]]

    if resource_id is not None:
        matching = [s for s in matching if s["resource_id"] == resource_id]

    if not matching:
        return {
            "success": False,
            "result_text": (
                "That exact slot isn't available anymore — someone may have just booked it. "
                "Want me to check nearby times instead?"
            ),
        }

    chosen = random.choice(matching)  # random among valid options, whether auto-assigned or premium said "any"

    status = "pending" if service["requires_confirmation"] else "confirmed"
    end_time = (datetime.fromisoformat(chosen["start_time"]) +
                timedelta(minutes=service["duration_min"])).isoformat()

    try:
        get_supabase().table("bookings").insert({
            "tenant_id": tenant["id"],
            "user_id": user_id,
            "service_id": service["id"],
            "resource_id": chosen["resource_id"],
            "start_time": chosen["start_time"],
            "end_time": end_time,
            "status": status,
            "source": "chatbot",
            "customer_name_manual": customer_name or None,
        }).execute()
    except Exception as err:
        print(f"create_booking insert failed: {err}")
        return {"success": False, "result_text": "Something went wrong saving that booking — nothing was confirmed. Please try again."}

    when = datetime.fromisoformat(chosen["start_time"]).strftime("%A, %b %d at %I:%M %p")

    # Notify the artist for real, if we have a real contact on file.
    # Silent no-op otherwise (placeholder artists have no channel_contact
    # yet) — this is exactly the "not live until real Telegram IDs exist"
    # boundary from artist_receptionist_roles_migration.sql.
    resource_row = next((r for r in _get_active_resources(tenant["id"]) if r["id"] == chosen["resource_id"]), None)
    if resource_row and resource_row.get("channel_contact"):
        notify_text = (
            f"New booking: {service['name']} on {when}"
            + (f" for {customer_name}" if customer_name else "")
            + (". Needs your confirmation." if status == "pending" else ". Confirmed.")
        )
        notified = await send_channel_message(
            resource_row.get("channel", "telegram"), resource_row["channel_contact"], notify_text
        )
        if not notified:
            print(f"create_booking: artist notification failed to send for booking at {when} (booking itself still saved)")

    if status == "confirmed":
        return {
            "success": True,
            "result_text": f"Booked: {service['name']} with {chosen['resource_name']} on {when}. Confirmed.",
        }
    return {
        "success": True,
        "result_text": (
            f"Requested: {service['name']} with {chosen['resource_name']} on {when}. "
            "This one needs a quick human confirmation first — you'll hear back shortly."
        ),
    }


# ─────────────────────────────────────────────────────────────────
# Tool-calling — same Groq raw tool-calling pattern as owner_tools.py.
#
# THE premium/non-premium split lives here, enforced structurally: two
# DIFFERENT tool schemas. The standard schema's book_appointment has no
# resource/artist parameter AT ALL — the model cannot request one because
# it does not exist for this conversation, not because it was told not
# to. Same lesson as the false-action-confirmation bug: hard constraints
# belong in code, not in a prompt sentence hoping the model complies.
# ─────────────────────────────────────────────────────────────────

import asyncio
import json

import llm_router  # for call_tool_with_fallback — real Groq->Gemini fallback,
                    # added 2026-07-26 after Groq hit its daily token cap
                    # mid-testing with zero fallback wired in


def _format_slots(slots: list[dict], include_artist: bool, limit: int = 24) -> str:
    if not slots:
        return "No open slots found for that day."
    if include_artist:
        lines = [f"{s['resource_name']} — {datetime.fromisoformat(s['start_time']).strftime('%I:%M %p')}"
                  for s in slots[:limit]]
    else:
        # Dedup by time only — a non-premium customer doesn't get to see
        # or pick which artist, so showing 4x the same time is just noise.
        seen_times = []
        for s in slots:
            t = datetime.fromisoformat(s['start_time']).strftime('%I:%M %p')
            if t not in seen_times:
                seen_times.append(t)
        lines = seen_times[:limit]
    return ", ".join(lines)


def _normalize_date(date_str: str) -> str:
    """Customers (and the LLM extracting from them) naturally say 'today'/
    'tomorrow' regardless of what the tool schema asks for — found crashing
    live 2026-07-26 (ValueError on 'today' passed straight to strptime).
    Normalize the common cases.

    Also guards against a real, separate bug found the same night: when
    NO date was actually stated by the customer, the model sometimes
    HALLUCINATES a plausible-looking but wrong date (observed: '2024-03-15',
    '2024-02-22' — a different YEAR entirely, always in the past). Any
    date that's empty, unparseable, or genuinely in the past is nonsensical
    for a salon booking (nobody books yesterday) — default to today rather
    than trust it blindly."""
    s = (date_str or "").strip().lower()
    today = _local_now().date()
    if s in ("today", "aaj"):
        return today.isoformat()
    if s in ("tomorrow", "kal"):
        return (today + timedelta(days=1)).isoformat()
    try:
        parsed = datetime.strptime(date_str or "", "%Y-%m-%d").date()
        if parsed < today:
            return today.isoformat()
        return date_str
    except ValueError:
        return today.isoformat()


def save_booking_context(tenant_id: int, user_id: int, service_id: int, booking_date: str) -> None:
    """Records 'this customer just saw times for service X on date Y' so
    a bare follow-up like '4pm' can be booked deterministically instead
    of relying on the LLM to re-infer the whole conversation's state."""
    try:
        get_supabase().table("booking_context").upsert({
            "tenant_id": tenant_id, "user_id": user_id,
            "service_id": service_id, "booking_date": booking_date,
        }, on_conflict="tenant_id,user_id").execute()
    except Exception as err:
        print(f"save_booking_context failed (non-fatal): {err}")


def clear_booking_context(tenant_id: int, user_id: int) -> None:
    """Explicit 'start over' — deletes any saved context so a stale
    service/date can't get silently reused. Deliberately checked BEFORE
    the LLM tool-decision call in decide_and_run_booking_tool (see
    RESET_PHRASES) — no reason to spend a Groq call guessing whether
    someone typing 'start over' wants to start over."""
    try:
        get_supabase().table("booking_context").delete() \
            .eq("tenant_id", tenant_id).eq("user_id", user_id).execute()
    except Exception as err:
        print(f"clear_booking_context failed (non-fatal): {err}")


def cancel_most_recent_booking(tenant_id: int, user_id: int) -> dict:
    """Cancels the customer's most recent non-cancelled booking. The
    'cancelled' status already existed in the bookings table's CHECK
    constraint since the schema was first written — nothing ever
    actually SET it until now; there was no way for a customer to
    cancel anything through the bot. Deterministic, code-decided result,
    same discipline as every other booking action tonight."""
    try:
        rows = (
            get_supabase()
            .table("bookings")
            .select("id, service_id, start_time")
            .eq("tenant_id", tenant_id).eq("user_id", user_id)
            .not_.in_("status", ["cancelled", "completed"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        if not rows:
            return {"result_text": "I don't see an active booking for you to cancel."}

        booking = rows[0]
        get_supabase().table("bookings").update({"status": "cancelled"}) \
            .eq("id", booking["id"]).execute()

        service = _get_service(tenant_id, booking["service_id"])
        when = datetime.fromisoformat(booking["start_time"]).strftime("%A, %b %d at %I:%M %p")
        name = service["name"] if service else "your appointment"
        return {"result_text": f"Cancelled: {name} on {when}."}
    except Exception as err:
        print(f"cancel_most_recent_booking failed: {err}")
        return {"result_text": "Something went wrong cancelling that — please try again or contact us directly."}


RESET_PHRASES = ("start over", "start fresh", "start a new", "reset", "never mind", "forget that")


def cancel_booking_for_customer(tenant_id: int, name_fragment: str) -> dict:
    """STAFF-ONLY (receptionist/admin/founder) version — cancels a named
    CUSTOMER's booking, not the caller's own. Only reachable via the
    is_staff tool schema (see _tools_schema) — a regular customer never
    sees this tool exist, only cancel_booking (self-only). Matches by
    display_name since the users table has no phone/email column to
    search by yet."""
    try:
        matches = (
            get_supabase().table("users").select("id, display_name")
            .eq("tenant_id", tenant_id)
            .ilike("display_name", f"%{name_fragment}%")
            .execute()
        ).data or []
    except Exception as err:
        print(f"cancel_booking_for_customer lookup failed: {err}")
        return {"result_text": "Something went wrong looking that customer up."}

    if not matches:
        return {"result_text": f"I couldn't find a customer named '{name_fragment}'."}
    if len(matches) > 1:
        names = ", ".join(m["display_name"] or "Unknown" for m in matches)
        return {"result_text": f"Multiple customers match '{name_fragment}': {names}. Could you be more specific?"}

    target_user_id = matches[0]["id"]
    clear_booking_context(tenant_id, target_user_id)
    return cancel_most_recent_booking(tenant_id, target_user_id)


def get_booking_context(tenant_id: int, user_id: int, max_age_minutes: int = 20) -> dict | None:
    """Returns the customer's most recent booking context, or None if
    there isn't one or it's gone stale (avoids booking against a service/
    date the customer asked about 3 hours ago and probably forgot)."""
    try:
        rows = (
            get_supabase()
            .table("booking_context")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .execute()
        ).data or []
        if not rows:
            return None
        ctx = rows[0]
        updated = datetime.fromisoformat(ctx["updated_at"].replace("Z", "+00:00"))
        age_min = (datetime.now(updated.tzinfo) - updated).total_seconds() / 60
        return ctx if age_min <= max_age_minutes else None
    except Exception as err:
        print(f"get_booking_context failed (non-fatal): {err}")
        return None


import re as _re

_TIME_ONLY_PATTERN = _re.compile(
    r"^\s*(\d{1,2})(?::(\d{2}))?\s*([a-zA-Z]{0,3})?\s*[.!?]?\s*$"
)


def parse_time_only(text: str) -> str | None:
    """Returns 'HH:MM' (24h) if the message is JUST a time and nothing
    else (e.g. '4pm', '4:30 PM', '16:00', even a typo'd '2 om') — the
    deterministic shortcut only fires on genuinely unambiguous bare-time
    replies, never on a full sentence, so it can't misfire on an
    unrelated short message. Trailing punctuation ('2pm?') is tolerated;
    an am/pm-ish suffix that doesn't clearly start with 'a' or 'p'
    (typos like 'om') falls back to the same PM-bias rule as no suffix
    at all — found live 2026-07-26 that a real typo ('2 om') otherwise
    fell through to the LLM instead of booking directly."""
    m = _TIME_ONLY_PATTERN.match(text)
    if not m:
        return None
    hour, minute, suffix = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if suffix.startswith("p") and hour != 12:
        hour += 12
    elif suffix.startswith("a") and hour == 12:
        hour = 0
    elif not suffix.startswith(("a", "p")) and hour <= 7:
        # No clear am/pm signal at all (or an unrecognized typo like 'om')
        # — assume PM for small hours, since 11am-8:30pm salon hours make
        # an early-morning booking rare and an ambiguous bare number more
        # often means afternoon.
        hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _find_resource_by_name(tenant_id: int, name_fragment: str) -> dict | None:
    name_lower = name_fragment.lower().strip()
    for r in _get_active_resources(tenant_id):
        if name_lower in r["name"].lower():
            return r
    return None


def _tools_schema(premium: bool, is_staff: bool = False) -> list[dict]:
    check_availability = {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check open appointment slots for a service on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["service_name", "date"],
            },
        },
    }

    book_properties = {
        "service_name": {"type": "string", "description": "The FIRST/primary service mentioned."},
        "additional_services": {
            "type": "array", "items": {"type": "string"},
            "description": "Any OTHER services the customer wants in the SAME visit, mentioned together with the first (e.g. 'nail art and hair color' -> service_name='nail art', additional_services=['hair color']). NEVER combine multiple services into one string in service_name.",
        },
        "date": {"type": "string", "description": "YYYY-MM-DD"},
        "time": {"type": "string", "description": "HH:MM, 24-hour — the START time; if multiple services, they're scheduled back-to-back from this time using each service's REAL duration."},
        "customer_name": {"type": "string"},
    }
    if premium:
        # ONLY premium customers get this parameter to exist at all.
        book_properties["preferred_artist"] = {
            "type": "string",
            "description": "Artist name if the customer asked for someone specific, or 'any' if they said no preference / pick randomly.",
        }

    book_appointment = {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment once a specific date+time has been confirmed available.",
            "parameters": {"type": "object", "properties": book_properties,
                            "required": ["service_name", "date", "time", "customer_name"]},
        },
    }

    if is_staff:
        # STAFF (receptionist/admin/founder) ONLY — a regular customer
        # never sees this tool exist at all, only the self-only version
        # below. Enforced by which schema gets built, same discipline as
        # the premium/non-premium artist-choice split.
        cancel_booking = {
            "type": "function",
            "function": {
                "name": "cancel_booking_for_customer",
                "description": "Cancel a NAMED customer's most recent active appointment. Staff/receptionist use — requires the customer's name.",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_name": {"type": "string", "description": "The customer's name to search for."}},
                    "required": ["customer_name"],
                },
            },
        }
    else:
        cancel_booking = {
            "type": "function",
            "function": {
                "name": "cancel_booking",
                "description": "Cancel the customer's OWN most recent active appointment. Only call when they clearly want to cancel an EXISTING booking, not when starting a new one.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }

    return [check_availability, book_appointment, cancel_booking]


def _system_prompt(premium: bool, is_staff: bool = False) -> str:
    today = _local_now()
    date_fact = (
        f"REAL current date: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')}). "
        "You have NO other way of knowing today's date — you do NOT have a "
        "calendar or live clock of your own, only this fact stated here. "
        "Compute 'today'/'tomorrow'/'this Friday'/etc. FROM this real date. "
        "NEVER invent or guess a date from your training data — that "
        "produces wrong, often years-old dates (found happening live "
        "2026-07-26: dates like '2024-03-15' were fabricated out of thin "
        "air when no date was actually given).\n\n"
    )
    cancel_tool_name = "cancel_booking_for_customer" if is_staff else "cancel_booking"
    staff_note = (
        "You are helping STAFF (receptionist/founder/admin), not a customer directly. "
        "cancel_booking_for_customer needs the customer's NAME — ask if it's not clear who.\n\n"
        if is_staff else ""
    )
    base = (
        date_fact + staff_note +
        "You help customers check availability and book salon appointments. "
        f"You have three tools: check_availability, book_appointment, and {cancel_tool_name}.\n\n"
        "Only call a tool when BOTH are true: (1) at least one specific "
        "service is named, and (2) the customer is clearly asking about "
        "timing/availability/booking for it — not just asking what it is, "
        "what it costs, or mentioning it in passing.\n\n"
        "CHECK vs BOOK — call the right one: if the customer clearly says "
        "'book'/'I'd like to book'/'please book' AND gives a specific date "
        "AND a specific time (not just a vague day), call book_appointment "
        "DIRECTLY — do not check availability as a separate step first; "
        "book_appointment itself will only succeed if that slot is "
        "actually free, so checking first is redundant and just slows "
        "things down. Only call check_availability when they're asking "
        "to SEE options without committing yet (e.g. 'what times do you "
        "have', 'is 3pm free').\n\n"
        "MULTIPLE SERVICES TOGETHER (e.g. 'nail art and hair color'): "
        "book_appointment supports this — put the first service in "
        "service_name and any others in additional_services (a list). "
        "NEVER combine multiple services into one string in service_name "
        "— that will fail to match anything. They'll be scheduled "
        "back-to-back starting from the given time, using each service's "
        "REAL duration (the customer's guessed total time window is not "
        "authoritative — the real durations are).\n\n"
        "Do NOT call a tool for:\n"
        "- A bare service name or short question like 'Waxing?' or 'Hair "
        "color?' — these are asking WHAT IT IS or general interest, not "
        "checking a time. Let the normal conversation answer these.\n"
        "- Questions about price, duration, artists, or location — none "
        "of these need a tool.\n\n"
        "When genuinely unsure whether they want to book, do NOT call a "
        "tool — a wrong guess (like dumping a full day's availability for "
        "an ambiguous one-word message) is worse than asking one "
        "clarifying question in normal conversation."
    )
    if not premium:
        base += (
            " This customer is NOT premium — you have no way to offer or "
            "mention choosing a specific artist, because that capability "
            "isn't available in this conversation. Never claim you can't "
            "assign a specific artist as a limitation — just proceed "
            "naturally with booking."
        )
    return base


def _parse_tool_args(raw_args) -> dict:
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return raw_args or {}


async def decide_and_run_booking_tool(text: str, tenant: dict, user_id: int | None,
                                       channel: str, channel_contact: str,
                                       history: list[dict] | None = None,
                                       effective_role: str | None = None) -> dict | None:
    """Returns {"result_text": ...} if a tool fired, or None if nothing
    matched (caller falls through to the normal conversational reply).
    Premium status is checked FIRST, before the model ever sees a tool
    schema — this decides which schema gets built, not just how the
    prompt is worded.

    history: recent prior turns (same shape as main.py's get_recent_history
    output), included so multi-turn flows resolve correctly — e.g.
    "show me haircut times tomorrow" -> "book it" needs the service/date
    from the PRIOR turn, which the model can't infer from "book it" alone.
    Found missing live 2026-07-26 (a real booking request silently fell
    through to plain chat instead of firing the tool)."""
    premium = is_premium_customer(tenant["id"], channel, channel_contact)
    is_staff = effective_role in ("receptionist", "admin", "founder")

    # Deterministic reset: no need to ask the LLM whether "start over"
    # means start over. Checked before anything else.
    if user_id is not None and any(p in text.strip().lower() for p in RESET_PHRASES):
        clear_booking_context(tenant["id"], user_id)
        return {"result_text": "Okay, starting fresh — what would you like to book?"}

    # Deterministic shortcut: if the customer just replied with a BARE
    # time ("4pm") and we have recent booking_context for them, book
    # directly instead of asking the LLM to re-infer the whole flow's
    # state from scratch. This is the real fix for the multi-turn bug
    # found live 2026-07-26 — the LLM kept re-listing availability
    # instead of recognizing "they already picked a slot, book it."
    if user_id is not None:
        bare_time = parse_time_only(text)
        if bare_time:
            ctx = get_booking_context(tenant["id"], user_id)
            if ctx:
                start_iso = f"{ctx['booking_date']}T{bare_time}:00"
                service_row = _get_service(tenant["id"], ctx["service_id"])
                if service_row:
                    return await create_booking(
                        tenant, service_name=service_row["name"], start_time_iso=start_iso,
                        resource_id=None, user_id=user_id, customer_name="",
                    )

    messages = [{"role": "system", "content": _system_prompt(premium, is_staff)}]
    for turn in (history or [])[-6:]:  # recent context only, keep the call cheap
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("content", "")})
    messages.append({"role": "user", "content": text})

    try:
        message = await llm_router.call_tool_with_fallback(
            messages, _tools_schema(premium, is_staff), timeout=20,
        )
    except Exception as err:
        print(f"decide_and_run_booking_tool: tool-decision call failed (non-fatal): {err}")
        return None

    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None

    call = tool_calls[0]["function"]
    name = call.get("name")
    args = _parse_tool_args(call.get("arguments"))
    print(f"DEBUG booking tool call: name={name!r} args={args!r} premium={premium}")

    try:
        if name == "check_availability":
            service = _get_service(tenant["id"], args.get("service_name", ""))
            if not service:
                return {"result_text": f"We don't have a service matching '{args.get('service_name', '')}' — want me to list what we do offer?"}
            date_str = _normalize_date(args.get("date", ""))
            slots = get_available_slots(tenant["id"], args.get("service_name", ""), date_str)
            if slots and user_id is not None:
                save_booking_context(tenant["id"], user_id, service["id"], date_str)
            formatted = _format_slots(slots, include_artist=premium)
            label = "Available times" if not premium else "Available"
            return {"result_text": f"{label}: {formatted}" if slots else f"No open slots found for {service['name']} on that day."}

        if name == "book_appointment":
            resource_id = None
            if premium:
                preferred = (args.get("preferred_artist") or "").strip().lower()
                if preferred and preferred != "any":
                    match = _find_resource_by_name(tenant["id"], preferred)
                    if match:
                        resource_id = match["id"]
            date_str = _normalize_date(args.get("date", ""))
            additional = [s for s in (args.get("additional_services") or []) if s.strip()]

            if not additional:
                start_iso = f"{date_str}T{args.get('time', '')}:00"
                return await create_booking(
                    tenant, service_name=args.get("service_name", ""), start_time_iso=start_iso,
                    resource_id=resource_id, user_id=user_id, customer_name=args.get("customer_name", ""),
                )

            # Multiple services in one visit: book each sequentially,
            # advancing the clock by each service's REAL duration — never
            # trusting a customer's guessed total window. Found missing
            # entirely live 2026-07-26 ("nail art and hair color together")
            # — book_appointment previously only ever supported one service.
            service_names = [args.get("service_name", "")] + additional
            cursor = datetime.fromisoformat(f"{date_str}T{args.get('time', '')}:00")
            outcomes = []
            for sname in service_names:
                svc = _get_service(tenant["id"], sname)
                if not svc:
                    outcomes.append(f"Couldn't find a service matching '{sname}' — skipped that one.")
                    continue
                outcome = await create_booking(
                    tenant, service_name=svc["name"], start_time_iso=cursor.isoformat(),
                    resource_id=resource_id, user_id=user_id, customer_name=args.get("customer_name", ""),
                )
                outcomes.append(outcome["result_text"])
                if outcome.get("success"):
                    cursor += timedelta(minutes=svc["duration_min"])
            return {"result_text": " ".join(outcomes)}

        if name == "cancel_booking":
            if user_id is None:
                return {"result_text": "I need your customer record to find a booking to cancel — please contact us directly."}
            clear_booking_context(tenant["id"], user_id)
            return cancel_most_recent_booking(tenant["id"], user_id)

        if name == "cancel_booking_for_customer":
            return cancel_booking_for_customer(tenant["id"], args.get("customer_name", ""))
    except Exception as err:
        # Any execution failure (bad date, malformed time, unexpected data
        # shape) degrades to an honest reply instead of a 500 — found this
        # crashing the whole request live 2026-07-26 on an unparseable date.
        print(f"decide_and_run_booking_tool: tool execution failed (non-fatal): {err}")
        return {"result_text": "Sorry, I couldn't process that — could you try rephrasing the date/time (e.g. 'tomorrow at 3pm')?"}

    return None
