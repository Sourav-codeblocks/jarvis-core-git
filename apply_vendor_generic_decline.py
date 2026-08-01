import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.vendor_decline_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_block = '''    if not vendor:
        if not _product_exists(tenant["id"], vendor_category, product_details):
            return {
                "success": False,
                "result_text": (
                    f"We don't currently carry '{product_details}' — "
                    f"{tenant['display_name']} specializes in pipe fittings "
                    "and related hardware. Happy to help if you're looking "
                    "for something from our catalog!"
                ),
            }
        return {
            "success": False,
            "result_text": (
                f"I couldn't find a vendor registered for '{vendor_category}' yet. "
                "No message was sent — you'll need to add that vendor first."
            ),
        }'''

new_block = '''    if not vendor:
        is_real_product = _product_exists(tenant["id"], vendor_category, product_details)
        print(
            f"[vendor-gap] tenant={tenant['id']} category='{vendor_category}' "
            f"product='{product_details}' in_catalog={is_real_product} -- "
            "no active vendor row matched; customer got a generic decline."
        )
        return {
            "success": False,
            "result_text": (
                f"Thanks for reaching out — let me check on that with the "
                f"{tenant['display_name']} team and get back to you shortly!"
            ),
        }'''

assert old_block in src, "expected block not found -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

target.write_text(src)
print("Patched: customer now always gets a generic decline; real vs out-of-catalog gap logged internally only.")
