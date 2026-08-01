import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.humanize_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_block = '''        return {
            "success": True,
            "result_text": (
                f"Good news, we stock that ourselves — {matched_product.get('name')}: "
                f"Rs {price_str} {unit}, currently {stock}. Let us know the quantity "
                "you'd like and we'll get your order moving."
            ),
        }'''

new_block = '''        return {
            "success": True,
            "result_text": (
                f"We've got that — {matched_product.get('name')} at Rs {price_str} "
                f"{unit}, {stock}. How many do you need?"
            ),
        }'''

assert old_block in src, "expected block not found -- aborting, no changes written"
src = src.replace(old_block, new_block, 1)

target.write_text(src)
print("Patched: shorter, more human catalog-match reply.")
