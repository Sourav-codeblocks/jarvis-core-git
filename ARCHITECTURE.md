# Jarvis Core — Architecture (living document)

**This file is REWRITTEN, not appended to.** `PROGRESS.md` is the diary —
it grows forever and that's fine. This file is the map — it should always
be short enough to read in five minutes and describe *only* what's true
right now.

Last rewritten: 2026-07-26, end of an extended session covering: droplet
resize, the booking engine, a real multi-provider outage during a live
demo, and the demo tenant. Anything marked **[unverified]** wasn't opened
this pass — confirm before relying on it.

---

## The One Rule

`tenant_id` flows through every table, every route. Adding a tenant is
config + data, never code — proven three times now (Keshri Pipes,
Mihika's Studio, the fictional demo tenant all run on identical code).

---

## Deployment reality (verified this session)

Droplet `159.89.166.167`, resized **1GB→2GB RAM, 1→2 vCPU, 25GB→60GB
disk** (was already swapping under one tenant before the resize — real,
not precautionary). Two separate folders/processes, NOT one shared
gateway:

```
/opt/jarvis-core         → Keshri Pipes, port 8000, jarvis-gateway.service
/opt/jarvis-core-mihika  → Mihika's Studio, port 8001, jarvis-gateway-mihika.service
```

**Known, deliberate limitation**: every shared code file (`main.py`,
`booking_tools.py`, `providers.py`, `llm_router.py`, `owner_tools.py`)
must be manually copied to BOTH folders on every change. This bit us
twice this session — once forgetting a redeploy, once a whole-file
rewrite silently reverting an SSH-only emergency fix because it was
built from a stale local copy instead of diffing against the live file
first. **The real fix (Docker: one shared image, per-tenant containers)
is scoped but not started.**

nginx routes both tenants' Telegram webhooks through one domain
(`159.89.166.167.sslip.io`) via path-based rules — `/webhook/telegram` →
8000, `/mihika/webhook/telegram` (rewritten) → 8001.

---

## LLM provider fallback — the most-tested part of this whole session

**Two separate fallback chains exist, both now 3 providers deep:**

1. **Plain conversational replies** (`llm_router.route()`, task_type
   `agent_turn`) — reads `model_registry` for live green/yellow/red
   status, tries certified candidates in chain order.
2. **Tool-calling** (`llm_router.call_tool_with_fallback()`, used by both
   `booking_tools.py` and — not yet — `founder_ws.py`) — a simpler,
   hardcoded chain, NOT gated by certification (a deliberate scope cut,
   not an oversight).

**Current chain (both), as of tonight:**
```
groq (llama-3.3-70b-versatile)
  → gemini (gemini-flash-lite-latest — NOT flash-latest, which has a
     much smaller 20/day quota and got exhausted)
    → openrouter (nvidia/nemotron-3-nano-30b-a3b:free — PINNED, not
       the auto-router "openrouter/free", which leaked raw internal
       text into a real customer reply)
```

**Real incident, not hypothetical:** all three of these were
simultaneously exhausted at least once tonight, under real (not
malicious) usage — proof that free-tier quotas are a genuine
constraint at even modest real volume. **Safety net added as a direct
result**: `main.py`'s final `ask_llm()` call is now wrapped in a
try/except — total provider failure degrades to an honest "having
trouble, please contact us" message, never silence. This is arguably
the single most important reliability fix of the whole session.

**Groq's paid Developer tier** (no minimum, ~$0.59/$0.79 per million
tokens for the 70B model) was attempted as a fix but is **currently
blocked by Groq's own signup outage** ("temporarily unavailable due to
high demand") — worth revisiting, likely the cheapest real fix once
their signup works again.

---

## Booking system — the other major build this session

Proven end-to-end on Mihika's Studio and the demo tenant. Key pieces:

- **`booking_tools.py`** — availability engine (real slot math, break-
  time buffers), deterministic booking creation (never LLM-narrated),
  multi-service booking (real sequential durations, never the
  customer's guessed time window), deterministic reset/cancel (checked
  BEFORE any LLM call — no guessing needed for these two), premium/
  non-premium artist choice (enforced by which TOOL SCHEMA exists, not
  a prompt instruction), staff-only cancel-for-customer (same
  schema-level enforcement).
- **`booking_context` table** — the fix for multi-turn booking ("show
  times" → bare "3pm" → books directly). **Was silently non-functional
  for a while this session because its migration was never run** even
  though the code was deployed — a real lesson: a code fix and its
  required schema change can drift apart with zero visible symptom
  beyond "the feature still doesn't work."
- **Timezone-aware, correctly** — server clock is UTC; `_local_now()`
  uses `zoneinfo` hardcoded to `Asia/Kolkata` for now. This was a real,
  live, DAILY-recurring bug before the fix (5.5 hrs/day where "today"
  resolved wrong), not a hypothetical one. Per-tenant timezone column
  is the correct long-term fix, not built yet — matters the moment a
  non-India tenant onboards.
- **`booking_template_GENERIC_schema.sql`** — the reusable, fully
  placeholder-ized version of the same 8-table structure, for any
  future appointment-based tenant.
- **`eval_booking_bot.py`** — real regression suite (deterministic +
  integration tiers), mirrors `eval_customer_bot.py`'s discipline. Run
  after ANY change to `booking_tools.py`. Caught a real prompt
  regression once already (over-corrected CHECK-vs-BOOK behavior).

**Known gap, not fully closed:** multi-service booking sometimes still
reaches `book_appointment` with a combined/mangled service name instead
of using the `additional_services` parameter correctly — the LLM
doesn't always follow the schema's intent perfectly. Same class of
limitation as everywhere else prompt-based tool selection is used.

---

## Identity & roles

`identities` + `channel_links` is the real system (NOT `users.role`,
which is superseded — see prior rewrite for why). Roles: `admin`,
`founder`, `staff`, `artist`, `receptionist`. Cross-tenant leak fixed
this session — `resolve_identity_role()` now correctly scopes lookups
to the current tenant; before the fix, one person's admin identity on
Tenant A leaked into Tenant B's conversations purely from sharing a
Telegram account.

**Seeded right now:** Sourabh = admin (Keshri Pipes only), Nikunj =
founder (Keshri Pipes only). Nobody seeded on Mihika's Studio or the
demo tenant yet. Gaurav still not seeded anywhere.

---

## Tenants (verified this session)

| Tenant | Type | Bot live? | Notes |
|---|---|---|---|
| Keshri Pipes | Catalog | Yes (Telegram) | Original tenant, most-tested |
| Mihika's Studio | Booking | Yes (Telegram) | First real second tenant, full incident history |
| Demo tenant (`demo-tenant`) | Catalog + Booking, combined | **No, deliberately** | Fictional "Glow Beauty Studio & Store." Data-only, validated via direct script, no bot stood up yet — build one only when actually needed for a live sales call. |
| Sunita Plastics | Unknown | Not started | Blocked — couldn't identify the real business from search; waiting on user to paste real info |
| My Dance Academy | Unknown | Not started | Next tenant, starting fresh |

---

## Known gaps (current, confirmed this session unless noted)

1. **Multi-provider exhaustion risk** — real, lived, not hypothetical.
   Mitigated (graceful fallback message) but not solved (paid tier
   blocked by Groq outage; GPU not yet provisioned).
2. **Docker not started** — the actual fix for the "edit every tenant
   folder separately" fragility that caused a real regression tonight.
3. **`founder_ws.py` has the identical single-provider gap** the
   booking layer had before tonight's fix — not yet given the same
   3-provider fallback chain.
4. Multi-service booking's `additional_services` isn't always used
   correctly by the model (see above).
5. `founder_reports.py` still stale (hardcoded `TENANT_ID = 1`) —
   long-standing, unrelated carryover.
6. `toleration.py` still dead code — long-standing, unrelated.
7. Eval/certification engine (`eval_api.py` etc.) still entirely
   undeployed — long-standing.
8. Real service durations/prices for Mihika's Studio still estimated,
   not confirmed with her directly.
9. Rajesh Bhai (real cement vendor) and Gaurav (founder identity) still
   not seeded with real contact info.
10. No receptionist has been seeded anywhere yet — the
    `cancel_booking_for_customer` capability exists but is untested
    against a real staff account.

---

## Quick reference — "where do I go to change X?"

| Want to... | Edit |
|---|---|
| Add/change a fallback provider | `llm_router.py`'s `TOOL_CALL_FALLBACK_CHAIN` (bookings) or `MODEL_MATRIX["agent_turn"]` (plain chat) — remember to update `model_registry` status too, and deploy to BOTH tenant folders |
| Onboard a new booking-type tenant | Copy `booking_template_GENERIC_schema.sql`, fill in placeholders |
| Check what's really deployed vs. just downloaded | `grep` the specific function/string directly on the server — don't trust memory, this session proved why |
| Diagnose a provider failure | Check the actual response body, not just the exception — `providers.py`'s raw builders now surface the real error text for exactly this reason |
| Test a booking-tenant change safely | `eval_booking_bot.py`, run before AND after any prompt/logic change |
