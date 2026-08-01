import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/payment_tools.py")
backup = target.with_suffix(".py.bak.classifier_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_import = "from datetime import date, timedelta\n\nfrom db_client import get_supabase\nfrom providers import get_raw_chat_call, normalize_tool_response"
new_import = "import asyncio\nfrom datetime import date, timedelta\n\nfrom db_client import get_supabase\nfrom providers import get_raw_chat_call"
assert old_import in src, "import block not found -- aborting"
src = src.replace(old_import, new_import, 1)

old_fn = '''async def _classify_payment_reply(text: str) -> str:
    """DELAYED | READY | OTHER. Deliberately narrow: only decides the
    CATEGORY, never drafts the reply -- copy is fixed, defined above."""
    provider, model = PAYMENT_TOOL_CHAIN[0]
    call = get_raw_chat_call(provider, model)
    messages = [
        {"role": "system", "content": (
            "Classify the customer's reply to a payment reminder into exactly "
            "one word: DELAYED (can't pay now / needs more time / will pay "
            "later), READY (ready to pay now / wants to arrange payment or "
            "collection), or OTHER (unrelated to this payment, unclear, or a "
            "question). Reply with exactly one of those three words, nothing else."
        )},
        {"role": "user", "content": text},
    ]
    raw = await call(messages=messages, tools=[], timeout=15)
    normalized = normalize_tool_response(provider, raw)
    content = (normalized.get("content") or "").strip().upper()
    if "READY" in content:
        return "READY"
    if "DELAYED" in content:
        return "DELAYED"
    return "OTHER"'''

new_fn = '''async def _classify_payment_reply(text: str) -> str:
    """DELAYED | READY | OTHER. Deliberately narrow: only decides the
    CATEGORY, never drafts the reply -- copy is fixed, defined above.
    Fails to OTHER on any error -- never touches payment state on a
    provider hiccup, same fail-safe spirit as owner_tools.py."""
    provider, model = PAYMENT_TOOL_CHAIN[0]
    try:
        raw = await asyncio.to_thread(
            get_raw_chat_call(provider, model),
            [
                {"role": "system", "content": (
                    "Classify the customer's reply to a payment reminder into "
                    "exactly one word: DELAYED (can't pay now / needs more "
                    "time / will pay later), READY (ready to pay now / wants "
                    "to arrange payment or collection), or OTHER (unrelated "
                    "to this payment, unclear, or a question). Reply with "
                    "exactly one of those three words, nothing else."
                )},
                {"role": "user", "content": text},
            ],
            [],
            15,
        )
        content = (raw["choices"][0]["message"].get("content") or "").strip().upper()
    except Exception as err:
        print(f"_classify_payment_reply: classification call failed (non-fatal, fails to OTHER): {err}")
        return "OTHER"
    if "READY" in content:
        return "READY"
    if "DELAYED" in content:
        return "DELAYED"
    return "OTHER"'''

assert old_fn in src, "classifier function not found -- aborting"
src = src.replace(old_fn, new_fn, 1)

target.write_text(src)
print("Patched: classifier now matches owner_tools.py's real call pattern.")
