import re
import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(f".py.bak.vendor_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

# 1. Add import
if "from catalog_store import get_all_products" not in src:
    src = src.replace(
        "from providers import get_raw_chat_call",
        "from providers import get_raw_chat_call\nfrom catalog_store import get_all_products",
        1,
    )

# 2. Insert helper function right before forward_to_vendor
helper = '''
def _product_exists(tenant_id: int, vendor_category: str, product_details: str) -> bool:
    """Real-catalog check: does this tenant actually carry something
    matching the requested category or product? Stops forward_to_vendor
    from firing -- and leaking an internal vendor-error message to a
    customer -- for things not actually sold (stationery, tape, etc).
    Word-overlap match, same shape as the dance-academy service-matching
    fix.
    """
    query_words = {
        w for w in re.findall(r"[a-z]+", f"{vendor_category} {product_details}".lower())
        if len(w) > 2
    }
    try:
        products = get_all_products(tenant_id, limit=200)
    except Exception as err:
        print(f"_product_exists: catalog lookup failed (non-fatal, fails open): {err}")
        return True

    for p in products:
        cat_words = set(re.findall(r"[a-z]+", p.get("category", "").lower()))
        name_words = set(re.findall(r"[a-z]+", p.get("name", "").lower()))
        if query_words & cat_words or query_words & name_words:
            return True
    return False


'''

marker = "async def forward_to_vendor("
assert marker in src, "forward_to_vendor not found -- aborting, no changes written"
if "_product_exists" not in src.split(marker)[0]:
    src = src.replace(marker, helper + marker, 1)

# 3. Patch the "if not vendor:" block to check catalog first
old_block = '''    if not vendor:
        return {
            "success": False,
            "result_text": (
                f"I couldn't find a vendor registered for '{vendor_category}' yet. "
                "No message was sent — you'll need to add that vendor first."
            ),
        }'''

new_block = '''    if not vendor:
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

assert old_block in src, "expected 'if not vendor:' block not found -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

target.write_text(src)
print("Patched owner_tools.py successfully.")
