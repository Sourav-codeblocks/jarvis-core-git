# Jarvis Core — Architecture (living document)

**This file is REWRITTEN, not appended to.** `PROGRESS.md` is the diary —
it grows forever and that's fine. This file is the map — it should always
be short enough to read in five minutes and describe *only* what's true
right now.

Last rewritten: 2026-08-01, end of a session covering: git baseline for
all tenant folders, Bug A diagnosis/fix (haircut example), a live vendor-
forwarding bug found and fixed, and a new payment follow-up feature for
Keshri Pipes. Anything marked **[unverified]** wasn't opened this pass —
confirm before relying on it.

---

## The One Rule

`tenant_id` flows through every table, every route. Adding a tenant is
config + data, never code — proven across Keshri Pipes, Mihika's Studio,
and My Dance Academy, all on the same underlying codebase.

---

## ⚠️ Next major change, not yet started: Docker + CI/CD

Explicit founder decision (2026-08-01): this is the top priority for the
next session, ahead of any new tenant. Reasoning: a single missing
`import re` briefly broke live order-forwarding mid-fix tonight, and
several other near-misses came from manual SSH patching under time
pressure. Everything below describing the "four separate folders,
manually kept in sync" deployment model is the CURRENT reality, but is
expected to change soon — re-verify this section first if reading it
more than a few weeks after the date above.

---

## Deployment reality (verified 2026-08-01)

Droplet `159.89.166.167` (2GB RAM / 2vCPU / 60GB disk). **Four folders,
NOT one shared gateway:**

```
/opt/jarvis-core          → Keshri Pipes      → port 8000 → jarvis-gateway.service
/opt/jarvis-core-mihika   → Mihika's Studio   → port 8001 → jarvis-gateway-mihika.service
/opt/jarvis-core-dance    → My Dance Academy  → port 8002 → jarvis-gateway-dance.service
/opt/jarvis-frontend      → Founder dashboard → port 3000 → jarvis-frontend.service — [unverified]
```

**Git status, all three tenant folders now under version control**
(closed 2026-08-01, was a real gap before): Keshri Pipes has a real
GitHub remote (`Sourav-codeblocks/jarvis-core-git`, branch
`droplet-live`) and is kept pushed. Mihika's Studio has local git only,
no remote yet. My Dance Academy was git-init'd for the first time this
session. `.env`/`venv`/`chroma_db` correctly gitignored in all three —
no secrets in any history.

**Known, deliberate limitation, unchanged**: shared code files (`main.py`,
`booking_tools.py`, `providers.py`, `llm_router.py`, `owner_tools.py`)
must be manually copied/patched per folder — there is no single source
of truth. **This session made it slightly worse on purpose**: Keshri
Pipes' `main.py`/`owner_tools.py` now carry a new `payment_tools.py`
integration and a vendor-forwarding fix that Mihika's/Dance's copies do
NOT have. This is intentional (payment follow-ups and vendor-forwarding
are catalog-tenant-specific, not needed by the two booking tenants) —
but it means "diff the folders before assuming they're identical" is now
more important than ever, not less. **Docker is the real fix**, per the
priority above.

nginx routes all three bots' Telegram webhooks by path:
`/webhook/telegram` → 8000, `/mihika/webhook/telegram` (rewritten) →
8001, `/dance/webhook/telegram` (rewritten) → 8002.

---

## Tenants (verified 2026-08-01)

| Tenant | Type | Bot live? | Notes |
|---|---|---|---|
| Keshri Pipes | Catalog | Yes (Telegram) | Original tenant, most-tested, has git+remote, has payment follow-ups (new) |
| Mihika's Studio | Booking | Yes (Telegram) | Second tenant, git but no remote |
| My Dance Academy | Booking | Yes (Telegram) | Third tenant, git added this session |
| Demo tenant (`demo-tenant`) | Catalog+Booking combined | No, deliberately | Fictional "Glow Beauty Studio & Store," data-only |
| Sunita Plastics | Unknown | Not started | Blocked on real business info, long-standing |
| NXT Landspaces (real estate) | Leads + Booking | Not started | Fully spec'd, explicitly PARKED by founder decision — don't build without being asked |

---

## Payment follow-up reminders (new, 2026-08-01, Keshri Pipes only)

New feature, separate from the catalog/booking templates. Not on any
prior plan — built and tested live in one session.

- **`payment_followups` table** (Supabase): tracks customer, invoice,
  amount, due date, status (`pending` → `reminder_sent` →
  `delayed_promised` / `agent_action_required` → `paid`/`cancelled`),
  `follow_up_count`, notes.
- **`payment_tools.py`** (new file, Keshri-only): same "code decides
  success/failure, LLM never narrates" discipline as `owner_tools.py`.
  Owner-triggered send ("send payment reminder to X") + customer-reply
  classification (DELAYED / READY / OTHER, one cheap Groq call).
- **Gated on STATE, not message content** — the classifier only ever
  runs for a sender who currently has an open `reminder_sent` row. This
  is what prevents a customer saying "can't pay today" while placing an
  unrelated order from ever touching payment state — the only reliable
  signal that a message is a reply to OUR reminder is that we ourselves
  just sent one and haven't resolved their reply yet.
- **Tested live 2026-08-01**: owner-send → DELAYED customer reply → state
  update, confirmed via real Telegram round-trip + DB check.
- **NOT yet tested**: the READY (cash-collection, dual-founder alert)
  path, and the 3rd-follow-up date-escalation copy. Both are written and
  deployed, just unexercised — verify before trusting live.
- **Still a real gap, separate table**: Keshri only has ONE row in the
  unrelated `vendors` table (`cement`) — `forward_to_vendor` (the
  existing vendor-forwarding tool, fixed this session, see below) will
  correctly say "no vendor" for anything else until real vendor data is
  added.

---

## Vendor-forwarding fix (2026-08-01, Keshri Pipes only)

Found live, not pre-planned. Before the fix, `forward_to_vendor`
(`owner_tools.py`) would either falsely deny real catalog items or
falsely claim a forward succeeded for things not actually sold, and
leaked internal founder-facing text ("you'll need to add that vendor
first") straight to customers.

**Current, correct behavior** (three-way, confirmed via live test):
1. Item is genuinely in the catalog → bot answers directly with real
   price/stock, no forward.
2. Item isn't in the catalog but a real vendor category exists → genuine
   forward happens, clean customer-facing confirmation only (internal
   detail stays in the message sent to the vendor, never shown to the
   customer).
3. Neither → honest, distinct decline — no longer claims a forward
   happened when it didn't.

Matching is full-word-coverage against the CUSTOMER's own words
(`product_details`), not the LLM's own invented `vendor_category` label
— an earlier version matched against both and broke on generic words
like "supplier" not appearing in any real product name.

Company profile (`data/keshri/company_profile.md`, reloaded via
`load_company_profile.py`) now correctly directs full-catalog requests
to the real website (`https://keshripipes.com`) instead of the model
improvising a fallback. **Note**: the loader does NOT auto-clear
`resolve_tenant()`'s cache — a gateway restart is required after any
profile reload, or the change won't take effect (cost real time
tonight before this was understood).

---

## Bugs — status as of 2026-08-01

### Bug A — hardcoded "haircut" example — FIXED
Confirmed a copy-paste bug in shared `_system_prompt()`
(`booking_tools.py`), NOT a cross-tenant data leak. Fixed and deployed
identically across all three tenants.

### Bug B — dateless booking loop on "11 am" (My Dance Academy) — STILL OPEN
Not diagnosed across three sessions now. Customer flow: asks for a class
→ studio-vs-home → "At home" → bot lists times with no date ever
established → "11 am" → same list repeats → never books. Needs real
code + log reading in `booking_tools.py` (`parse_time_only` +
`booking_context`), not another live guess. Live customer-facing bug —
worth prioritizing on its own merits, independent of the Docker work.

### Vendor-forwarding bug — FIXED (2026-08-01)
See section above. Keshri Pipes only, code fix confirmed live.

---

## Identity & roles [unverified this pass — carried from prior rewrite]

`identities` + `channel_links`, tenant-scoped. Roles: `admin`, `founder`,
`staff`, `artist`, `receptionist`. Keshri Pipes has two verified admin/
founder identities (Sourabh, Nikunj) — confirmed live 2026-08-01, used
to alert both on the payment follow-up READY path. Other tenants'
identity seeding not re-checked this pass.

---

## Frontend — open discrepancy, needs resolving

`README.md` (as of its last update) describes `founders-core/` as the
primary live voice UI (Deepgram STT/TTS, port 3000, deployed on the VM).
`SESSION_HANDOFF_v2.md` separately describes `/opt/jarvis-frontend` — a
TanStack Start + Bun + shadcn/ui dashboard, ALSO port 3000 — as
something nobody in that session knew existed. **These may be the same
thing under a different name, one may have replaced the other, or they
may be two genuinely different unverified frontends.** Not resolved as
of this rewrite — top investigation item for next session alongside
Docker/CI-CD.

---

## Known gaps (current, confirmed 2026-08-01 unless noted)

1. **Docker not started** — top priority next session, see above.
2. **Bug B (dateless booking loop)** — still open, three sessions running.
3. **Frontend identity discrepancy** — see section above.
4. **Shared-file drift** — Keshri's `main.py`/`owner_tools.py` now ahead
   of Mihika's/Dance's copies (payment tools, vendor fix) — deliberate,
   but a real "don't assume folders are identical" risk until Docker
   consolidates this.
5. **Payment follow-ups READY path + 3rd-followup escalation** — written,
   deployed, not yet live-tested.
6. **Keshri's real vendor list** — only `cement` registered; get the
   real list from Keshri directly.
7. **Groq quota observability** — silent fallback on exhaustion, logs
   failure only, never success. Long-standing, unfixed.
8. Everything in the "Known gaps" section of the 2026-07-26 rewrite not
   explicitly re-verified above (multi-provider exhaustion mitigations,
   `founder_ws.py`'s fallback chain, eval engine reconciliation, etc.)
   — **[unverified]**, wasn't re-checked this session. Don't assume
   still accurate without confirming.

---

## Quick reference — "where do I go to change X?"

| Want to... | Edit |
|---|---|
| Change Keshri's payment reminder or reply copy | `payment_tools.py` — `REMINDER_TEMPLATE`, `REPLY_DELAYED*`, `REPLY_READY` |
| Change vendor-forwarding logic | `owner_tools.py` — `forward_to_vendor`, `_find_matching_product` |
| Update Keshri's company facts (address, brands, website, etc.) | Edit `data/keshri/company_profile.md`, then run `load_company_profile.py`, then RESTART the gateway |
| Apply a shared-file fix safely | Self-contained `apply_*.py` patch script pattern (backup, exact-match assert, `py_compile`, verify with `grep` for both new AND absent-old text) — see `COMMANDS.md` |
| Check what's really deployed vs. just downloaded | `grep` the specific function/string directly on the server — don't trust memory |
| Diagnose a provider failure | Check the actual response body, not just the exception |
