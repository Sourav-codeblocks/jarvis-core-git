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


def _get_service(tenant_id: int, service_name_or_id) -> dict | None:
    q = get_supabase().table("services").select("*").eq("tenant_id", tenant_id).eq("is_active", True)
    if isinstance(service_name_or_id, int):
        q = q.eq("id", service_name_or_id)
    else:
        q = q.ilike("name", f"%{service_name_or_id}%")
    rows = q.execute().data or []
    return rows[0] if rows else None


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
