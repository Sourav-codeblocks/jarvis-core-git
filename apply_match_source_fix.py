import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.match_source_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_line = '''    query_words = {
        w for w in re.findall(r"[a-z]+", f"{vendor_category} {product_details}".lower())
        if len(w) > 2
    }'''

new_line = '''    # Match against what the CUSTOMER actually asked for, not the LLM's
    # own vendor_category label -- generic words like "supplier"/"dealer"
    # in that label were breaking full-coverage matching against real
    # product names (found live: "tape supplier" failed to match "Teflon
    # Tape" because "supplier" isn't part of any product name).
    query_words = {
        w for w in re.findall(r"[a-z]+", product_details.lower())
        if len(w) > 2
    }'''

assert old_line in src, "expected query_words block not found -- aborting, no changes written"
src = src.replace(old_line, new_line, 1)

target.write_text(src)
print("Patched: catalog match now uses product_details only.")
