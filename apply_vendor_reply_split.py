import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.reply_split_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_block = '''    if sent:
        return {
            "success": True,
            "result_text": f"Sent to {vendor['name']} on {vendor['channel']}. They'll have it now.",
        }'''

new_block = '''    if sent:
        return {
            "success": True,
            "result_text": (
                f"We don't stock that ourselves, but I've forwarded your "
                f"request to our {vendor_category} supplier — they'll be in "
                "touch with you shortly."
            ),
        }'''

assert old_block in src, "success block not found -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

target.write_text(src)
print("Patched: customer sees a clean confirmation, not the internal vendor-forward text.")
