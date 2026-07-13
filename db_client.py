"""Jarvis Core — shared Supabase client factory + tenant resolution.

Pulled out of main.py so certify_model.py and llm_router.py don't each
create their own client / re-read env vars independently.

resolve_tenant() is the One Rule's actual entry point: every channel
(Telegram, founder WS, voice) hands this module a tenant_slug, and this
is the single place that turns it into the tenant_id (plus tier and
chroma_collection) everything downstream needs. Before this, main.py,
founder_ws.py, and voice_bridge.py each hardcoded tenant_id = 1
independently — three separate seams that all had to be edited by hand
to onboard tenant #2. Now there's one seam, and it's a DB lookup.
"""

import os
from functools import lru_cache
from supabase import create_client


@lru_cache(maxsize=1)
def get_supabase():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )


class UnknownTenant(Exception):
    """Raised when a tenant_slug doesn't match any row in `tenants`.

    Callers should turn this into a clean 404/close-the-connection
    response rather than letting it bubble up as a raw 500 — an unknown
    slug is a routing/config problem (bad URL, stale bot token mapping,
    typo'd env var), not a server crash.
    """


@lru_cache(maxsize=64)
def resolve_tenant(tenant_slug: str) -> dict:
    """Look up a tenant's row by slug.

    Returns the columns every channel needs to operate correctly for
    that tenant: id (for every FK), tier (for cloud-model gating in
    llm_router.py), and chroma_collection (for per-tenant RAG — the
    One Rule applies to knowledge too, see ingest.py).

    Cached because this runs on every webhook POST / WS connect and
    tenant rows change rarely. If you edit a tenant's row (e.g. tier
    upgrade, chroma_collection rename) and need it to take effect
    without restarting the gateway, call resolve_tenant.cache_clear().
    """
    result = (
        get_supabase()
        .table("tenants")
        .select("id, slug, display_name, tier, chroma_collection")
        .eq("slug", tenant_slug)
        .execute()
    )
    if not result.data:
        raise UnknownTenant(f"No tenant with slug={tenant_slug!r}")
    return result.data[0]
