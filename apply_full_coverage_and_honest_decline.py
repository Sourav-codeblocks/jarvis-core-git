import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.full_coverage_fix")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

# 1. Tighten the match: require ALL meaningful query words present in the
#    same field (name or category), not just any one shared word. Fixes
#    "bori cement" incorrectly matching "Solvent Cement" on the word
#    "cement" alone -- same class of fix as the dance-academy v4 patch.
old_match = '''        if query_words & cat_words or query_words & name_words:
            return p'''
new_match = '''        if query_words and (query_words <= cat_words or query_words <= name_words):
            return p'''
assert old_match in src, "match line not found -- aborting, no changes written"
src = src.replace(old_match, new_match, 1)

# 2. Honest, distinct wording for "nothing in catalog, no vendor either"
#    -- no more implying a follow-up that never happened.
old_decline = '''        return {
            "success": False,
            "result_text": (
                f"Thanks for reaching out — let me check on that with the "
                f"{tenant['display_name']} team and get back to you shortly!"
            ),
        }'''
new_decline = '''        return {
            "success": False,
            "result_text": (
                f"We don't currently carry that, sorry! "
                f"{tenant['display_name']} specializes in pipes, fittings, "
                "valves, and related consumables — happy to help if you're "
                "looking for something from that range."
            ),
        }'''
assert old_decline in src, "decline text not found -- aborting, no changes written"
src = src.replace(old_decline, new_decline, 1)

target.write_text(src)
print("Patched: full word-coverage matching + honest no-match decline text.")
