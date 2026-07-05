"""Toleration middleware — runs BEFORE the tenant's LangGraph is invoked.

Flow per incoming message:
  1. Cheap intent check: business vs offtopic (tiny local model — near-zero cost).
  2. Read today's strike state from Postgres.
  3. Decide: PASS | SOFT_REDIRECT | HARD_IGNORE.
  4. Increment counters and set timeouts as needed.

Design notes:
- The offtopic classifier itself must be CHEAP. Use the smallest model in the
  matrix (see llm_router.py), or even keyword heuristics first, then model.
- Copy is deliberately softer than "you are costing us compute" — same control,
  better customer experience.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Thresholds from the spec, adjusted by reputation.
BASE_SOFT_LIMIT = 3      # strikes before soft redirect messaging
BASE_HARD_LIMIT = 9      # strikes before hard ignore
TIMEOUT_HOURS = 24


@dataclass
class TolerationDecision:
    action: str            # 'PASS' | 'SOFT_REDIRECT' | 'HARD_IGNORE'
    reply_override: str | None = None


def limits_for(reputation: int) -> tuple[int, int]:
    """High-reputation users (consistent orders, good KPIs) get more slack."""
    bonus = 0
    if reputation >= 80:
        bonus = 2
    elif reputation >= 65:
        bonus = 1
    return BASE_SOFT_LIMIT + bonus, BASE_HARD_LIMIT + bonus


def classify_offtopic(message: str, tenant_business_desc: str, llm_call) -> bool:
    """llm_call is injected (see llm_router.route) so this file stays model-agnostic."""
    prompt = (
        f"Business context: {tenant_business_desc}\n"
        f"Customer message: {message}\n"
        "Is this message related to the business (orders, products, payments, "
        "support, scheduling)? Answer only YES or NO."
    )
    answer = llm_call(task_type="intent", prompt=prompt).strip().upper()
    return answer.startswith("NO")


def apply_toleration(db, user, message: str, tenant, llm_call) -> TolerationDecision:
    state = db.get_moderation_state(user_id=user.id)  # today's row, auto-create

    # Already in timeout?
    now = datetime.now(timezone.utc)
    if state.hard_ignore_until and now < state.hard_ignore_until:
        # Still respond to clearly business-critical intents even during timeout.
        if not classify_offtopic(message, tenant.business_desc, llm_call):
            return TolerationDecision(action="PASS")
        return TolerationDecision(action="HARD_IGNORE")

    if not classify_offtopic(message, tenant.business_desc, llm_call):
        return TolerationDecision(action="PASS")

    # Off-topic: increment strike and decide.
    soft_limit, hard_limit = limits_for(user.reputation)
    count = db.increment_offtopic(user_id=user.id)

    if count <= soft_limit:
        return TolerationDecision(action="PASS")  # indulge gracefully, 1-2 msgs

    if count < hard_limit:
        return TolerationDecision(
            action="SOFT_REDIRECT",
            reply_override=(
                "Happy to chat! Though I'm mainly here to help you with "
                f"{tenant.display_name} — orders, products, payments. "
                "Anything I can help you with on that front?"
            ),
        )

    db.set_hard_ignore(user_id=user.id, until=now + timedelta(hours=TIMEOUT_HOURS))
    return TolerationDecision(action="HARD_IGNORE")
