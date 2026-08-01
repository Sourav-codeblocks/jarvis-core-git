import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.three_way_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

# 1. Replace the boolean helper with one that returns the actual matched product
old_helper_start = 'def _product_exists(tenant_id: int, vendor_category: str, product_details: str) -> bool:'
assert old_helper_start in src, "helper function not found -- aborting, no changes written"

old_helper = '''def _product_exists(tenant_id: int, vendor_category: str, product_details: str) -> bool:
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
    return False'''

new_helper = '''def _find_matching_product(tenant_id: int, vendor_category: str, product_details: str) -> dict | None:
    """Real-catalog check: does this tenant actually stock something
    matching the requested category or product? Returns the matched
    product ROW itself (not just True/False) so the caller can answer
    with real price/stock instead of forwarding somewhere for an item
    already on the shelf. Word-overlap match, same shape as the
    dance-academy service-matching fix. On a DB error, returns None
    (fails SAFE -- falls through to the vendor/decline path -- rather
    than fabricating a fake product match).
    """
    query_words = {
        w for w in re.findall(r"[a-z]+", f"{vendor_category} {product_details}".lower())
        if len(w) > 2
    }
    try:
        products = get_all_products(tenant_id, limit=200)
    except Exception as err:
        print(f"_find_matching_product: catalog lookup failed (non-fatal, fails safe): {err}")
        return None

    for p in products:
        cat_words = set(re.findall(r"[a-z]+", p.get("category", "").lower()))
        name_words = set(re.findall(r"[a-z]+", p.get("name", "").lower()))
        if query_words & cat_words or query_words & name_words:
            return p
    return None'''

assert old_helper in src, "helper body doesn't match exactly -- aborting, no changes written"
src = src.replace(old_helper, new_helper, 1)

# 2. Insert the catalog short-circuit before the vendor lookup, and simplify
#    the no-vendor branch (it can no longer be reached for real catalog items)
old_block = '''    vendor = find_vendor(tenant["id"], vendor_category)

    if not vendor:
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

new_block = '''    matched_product = _find_matching_product(tenant["id"], vendor_category, product_details)
    if matched_product:
        price = matched_product.get("price_inr_per_unit")
        price_str = f"{price:g}" if isinstance(price, (int, float)) else str(price)
        if price_str.endswith(".00"):
            price_str = price_str[:-3]
        stock = str(matched_product.get("stock_status", "")).replace("_", " ")
        unit = matched_product.get("unit", "")
        return {
            "success": True,
            "result_text": (
                f"Good news, we stock that ourselves — {matched_product.get('name')}: "
                f"Rs {price_str} {unit}, currently {stock}. Let us know the quantity "
                "you'd like and we'll get your order moving."
            ),
        }

    vendor = find_vendor(tenant["id"], vendor_category)

    if not vendor:
        print(
            f"[vendor-gap] tenant={tenant['id']} category='{vendor_category}' "
            f"product='{product_details}' -- not in our catalog, no active vendor "
            "row matched either; customer got a generic decline."
        )
        return {
            "success": False,
            "result_text": (
                f"Thanks for reaching out — let me check on that with the "
                f"{tenant['display_name']} team and get back to you shortly!"
            ),
        }'''

assert old_block in src, "vendor block doesn't match exactly -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

target.write_text(src)
print("Patched: catalog items answered directly, vendor items forwarded for real, everything else declines politely.")
