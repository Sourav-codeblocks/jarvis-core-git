import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/main.py")
backup = target.with_suffix(".py.bak.payment_hook")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_block = '''    reply = None
    if effective_role in ("admin", "founder"):
        tool_result = await owner_tools.decide_and_run_owner_tool(
            text, tenant, requester_name=identity_name or display_name
        )
        if tool_result is not None:
            reply = tool_result["result_text"]'''

new_block = '''    reply = None

    # Payment-followup reply check -- runs for EVERY sender, not just
    # admins, since customers are who reply to reminders. Gated entirely
    # on STATE (does this exact sender have an open reminder_sent row?),
    # not on message content -- a true no-op for anyone who was never
    # sent a reminder, so this can never affect a normal order/catalog
    # conversation. See payment_tools.py's decide_and_run_payment_reply
    # docstring for the full reasoning.
    payment_result = await payment_tools.decide_and_run_payment_reply(
        text, tenant, channel="telegram", channel_contact=str(sender["id"]),
    )
    if payment_result is not None:
        reply = payment_result["result_text"]

    if reply is None and effective_role in ("admin", "founder"):
        tool_result = await owner_tools.decide_and_run_owner_tool(
            text, tenant, requester_name=identity_name or display_name
        )
        if tool_result is not None:
            reply = tool_result["result_text"]'''

assert old_block in src, "expected block not found -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

old_import_marker = "import owner_tools" if "import owner_tools" in src else None
if old_import_marker:
    src = src.replace(old_import_marker, old_import_marker + "\nimport payment_tools", 1)
else:
    # owner_tools referenced without a plain "import owner_tools" line --
    # find how it's actually imported instead of guessing.
    print("WARNING: could not find 'import owner_tools' to anchor the new import -- add 'import payment_tools' near the top of main.py by hand.")

target.write_text(src)
print("Patched: payment-reply check wired into telegram_webhook, before the owner-tools branch.")
