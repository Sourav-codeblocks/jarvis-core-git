"""Jarvis Core — Eval subject: customer bot, end-to-end.

Why this exists alongside eval_cases.py / eval_graph.py: that grid tests
the MODEL against a simulated production prompt. But the two bugs that
actually hit production this week — 'kp005 not in catalog' (2026-07-14)
and the 4-item 'full catalog' (2026-07-14) — were RETRIEVAL bugs. The
model behaved perfectly both times; it was handed the wrong context.
Model-only evals can never catch that class of failure.

So this suite calls main.ask_llm() itself: real Chroma retrieval, real
provider chain (Groq/Gemini), real tenant resolution. Ground truth is
parsed live from the tenant's own Chroma collection at run time — no
hardcoded prices that go stale when the catalog CSV changes.

RUN THIS ON THE VM (it needs the real chroma_db, .env keys, Supabase):
    cd /opt/jarvis-core && ./venv/bin/python3 eval_customer_bot.py

Notes:
- Each case is one real LLM call -> writes real usage_events rows and
  costs real (tiny) Groq tokens. That's the point: it's the production
  path, exercised deliberately instead of by a paying customer.
- Every time a production message breaks the bot, add it here as a case,
  same regression philosophy as eval_cases.py.
"""

import asyncio
import re
import sys
from dataclasses import dataclass, field
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

import main  # noqa: E402  (imports after load_dotenv on purpose)
from db_client import resolve_tenant  # noqa: E402

TENANT_SLUG = main.TENANT_SLUG


# ── Ground truth, parsed live from the tenant's own collection ──────────

def load_catalog_truth(tenant: dict) -> dict:
    """Reads every document in the tenant's Chroma collection and parses
    the fields ingest.py wrote (see ingest.row_to_document for the exact
    format). Returns {product_id: {price, stock_status, moq, ...}}."""
    collection = main.get_catalog_collection(tenant["chroma_collection"])
    all_docs = collection.get(include=["documents", "metadatas"])
    truth: dict[str, dict] = {}
    for doc, meta in zip(all_docs["documents"], all_docs["metadatas"]):
        pid = meta["product_id"]
        price_m = re.search(r"Price: Rs (\d+)", doc)
        moq_m = re.search(r"Minimum order quantity: (\d+)", doc)
        truth[pid] = {
            "doc": doc,
            "price": price_m.group(1) if price_m else None,
            "moq": moq_m.group(1) if moq_m else None,
            "stock_status": meta.get("stock_status", ""),
            "category": meta.get("category", ""),
        }
    return truth


# ── Case definition ──────────────────────────────────────────────────────

@dataclass
class BotCase:
    label: str
    input_text: str
    # check(reply_lowercase, truth) -> (passed, reason)
    check: Callable[[str, dict], tuple[bool, str]]
    notes: str = ""


def _has(reply: str, *terms) -> bool:
    return all(t.lower() in reply for t in terms)


# Each check receives the lowercased reply and the live catalog truth.

def check_exact_price(pid: str):
    def check(reply: str, truth: dict):
        p = truth[pid]["price"]
        if p is None:
            return False, f"ground truth for {pid} has no parsable price"
        if pid.lower() not in reply:
            return False, f"reply never mentions {pid}"
        if p not in reply:
            return False, f"reply lacks the real price {p} for {pid}"
        return True, f"{pid} @ Rs {p} correctly stated"
    return check


def check_stock_status(pid: str):
    def check(reply: str, truth: dict):
        status = truth[pid]["stock_status"].replace("_", " ")
        if pid.lower() not in reply:
            return False, f"reply never mentions {pid}"
        # 'in_stock' -> accept 'in stock'/'available'; 'low_stock' -> 'low';
        # 'out_of_stock' -> 'out of stock'/'not available'
        ok = {
            "in stock": _has(reply, "stock") or "available" in reply or "uplabdh" in reply,
            "low stock": "low" in reply or "limited" in reply or "kam" in reply,
            "out of stock": "out of stock" in reply or "not available" in reply or "nahi" in reply,
        }.get(status, False)
        if not ok:
            return False, f"real status is '{status}' but reply doesn't reflect it"
        return True, f"{pid} status '{status}' correctly reflected"
    return check


def check_full_catalog(reply: str, truth: dict):
    ids = list(truth.keys())
    mentioned = [pid for pid in ids if pid.lower() in reply]
    coverage = len(mentioned) / len(ids)
    if coverage < 0.9:
        missing = sorted(set(ids) - set(mentioned))
        return False, (f"only {len(mentioned)}/{len(ids)} products listed; "
                       f"missing e.g. {missing[:5]}")
    return True, f"{len(mentioned)}/{len(ids)} products listed"


def check_category_pvc(reply: str, truth: dict):
    pvc_ids = [pid for pid, t in truth.items() if "PVC" in t["doc"] and "CPVC" not in t["doc"].split(".")[1]]
    if not any(pid.lower() in reply for pid in truth):
        return False, "reply names no product IDs at all"
    if "pvc" not in reply:
        return False, "reply never says PVC"
    return True, "mentions PVC products by ID"


def check_no_invented_price(reply: str, truth: dict):
    # KP999 doesn't exist — the reply must not state ANY 'rs <number>' price.
    if re.search(r"rs\.?\s*\d+", reply):
        return False, "stated a price for a nonexistent product"
    if not any(w in reply for w in ("check", "not", "team", "available", "nahi")):
        return False, "didn't clearly say the product is unknown"
    return True, "declined to invent a price for KP999"


def check_no_false_order_confirm(reply: str, truth: dict):
    banned = ("order placed", "order confirmed", "order has been placed",
              "successfully placed", "booked your order")
    for phrase in banned:
        if phrase in reply:
            return False, f"falsely claimed: '{phrase}' (no order flow exists)"
    return True, "did not fabricate an order confirmation"


def check_offtopic_deflect(reply: str, truth: dict):
    if "ingredient" in reply or "recipe" in reply and "pipe" not in reply:
        return False, "answered the off-topic request"
    return True, "stayed on business"


CASES = [
    BotCase(
        label="exact_code_price_kp005",
        input_text="What's the price of KP005?",
        check=check_exact_price("KP005"),
        notes="Regression: 2026-07-14 'kp005 not in catalog' — embedding "
              "search can't match codes; exact-match retrieval must.",
    ),
    BotCase(
        label="exact_code_lowercase_kp011",
        input_text="do you have kp011 in stock?",
        check=check_stock_status("KP011"),
        notes="Lowercase code + stock question in one.",
    ),
    BotCase(
        label="full_catalog_listing",
        input_text="show me the full product catalog please",
        check=check_full_catalog,
        notes="Regression: 2026-07-14 — bot presented top-4 retrieval as "
              "the 'full catalog'. Requires all-rows retrieval for "
              "list-everything intents.",
    ),
    BotCase(
        label="category_query_pvc",
        input_text="do you have pvc pipes?",
        check=check_category_pvc,
        notes="Semantic path — should keep working alongside exact-match.",
    ),
    BotCase(
        label="hinglish_price_kp003",
        input_text="kp003 ka price kya hai bhai?",
        check=check_exact_price("KP003"),
        notes="Hinglish + code together.",
    ),
    BotCase(
        label="nonexistent_product_kp999",
        input_text="what's the price of KP999?",
        check=check_no_invented_price,
        notes="Grounding: unknown code must not get an invented price.",
    ),
    BotCase(
        label="order_attempt_no_false_confirm",
        input_text="Give me 5 pieces of kp005, place the order now.",
        check=check_no_false_order_confirm,
        notes="No order flow exists yet — the bot must not claim one "
              "succeeded. (Helpful redirection is fine.)",
    ),
    BotCase(
        label="offtopic_recipe",
        input_text="Write me a recipe for butter chicken.",
        check=check_offtopic_deflect,
        notes="Mirror of eval_cases.py ood_recipe_request, but through the "
              "real pipeline.",
    ),
]


async def run() -> int:
    tenant = resolve_tenant(TENANT_SLUG)
    truth = load_catalog_truth(tenant)
    print(f"Catalog ground truth loaded: {len(truth)} products "
          f"from '{tenant['chroma_collection']}'\n")

    passed = 0
    failures = []
    for case in CASES:
        try:
            reply = await main.ask_llm(case.input_text, history=[], tenant=tenant)
        except Exception as err:
            print(f"[ERROR] {case.label}: pipeline raised: {err}\n")
            failures.append((case.label, f"pipeline error: {err}"))
            continue

        ok, reason = case.check(reply.lower(), truth)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case.label}")
        print(f"    Q: {case.input_text}")
        print(f"    A: {reply[:220]}{'...' if len(reply) > 220 else ''}")
        print(f"    -> {reason}\n")
        if ok:
            passed += 1
        else:
            failures.append((case.label, reason))

    print(f"{'='*60}\n{passed}/{len(CASES)} passed")
    if failures:
        print("\nFailures to fix (batch these):")
        for label, reason in failures:
            print(f"  - {label}: {reason}")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
