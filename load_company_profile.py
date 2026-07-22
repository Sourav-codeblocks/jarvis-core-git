"""Jarvis Core — load a tenant's company profile into the tenants table.

The markdown file (data/<tenant>/company_profile.md) is the human-editable
source of truth; the tenants.company_profile column is what the gateway
actually reads (via db_client.resolve_tenant). Same pattern as ingest.py:
edit the source file, re-run the loader, done.

Usage:
    python load_company_profile.py --tenant keshri-pipes \
        --file data/keshri/company_profile.md

IMPORTANT: resolve_tenant() is lru_cached inside the running gateway
process. After loading a new profile, restart the gateway (or add an
admin endpoint that calls resolve_tenant.cache_clear()) or the old
profile keeps being served from cache.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from db_client import get_supabase  # noqa: E402 (after load_dotenv on purpose)

MAX_PROFILE_CHARS = 8000  # keep the prompt small; ~2k tokens ceiling


def main() -> None:
    parser = argparse.ArgumentParser(description="Load company profile into tenants row.")
    parser.add_argument("--tenant", required=True, help="tenant slug, e.g. keshri-pipes")
    parser.add_argument("--file", required=True, help="path to company_profile.md")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"Profile file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if len(text) > MAX_PROFILE_CHARS:
        raise SystemExit(
            f"Profile is {len(text)} chars (max {MAX_PROFILE_CHARS}). "
            "Trim it — this whole block rides in every prompt."
        )

    supabase = get_supabase()
    result = (
        supabase.table("tenants")
        .update({"company_profile": text})
        .eq("slug", args.tenant)
        .execute()
    )
    if not result.data:
        raise SystemExit(
            f"No tenant with slug={args.tenant!r} — check the slug "
            "(and that schema_add_company_profile.sql has been run)."
        )

    print(f"Loaded {len(text)} chars into tenants.company_profile "
          f"for '{args.tenant}'. Restart the gateway to clear the "
          "resolve_tenant() cache.")


if __name__ == "__main__":
    main()
