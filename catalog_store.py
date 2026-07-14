"""Jarvis Core — catalog store: Supabase `products` is the truth,
Chroma is a derived index.

Why this module exists
----------------------
Before 2026-07-14, product prices/stock lived ONLY inside embedded text
strings in ChromaDB, written by ingest.py from a CSV. Three consumers each
depended on that string format independently: main.py's RAG prompt,
founder_ws.py's catalog report, and eval_customer_bot.py's ground-truth
parser. A price change meant re-running ingest and hoping every consumer's
parsing still lined up.

Now:
  - `products` table (products_schema.sql) holds the structured truth.
  - product_to_document() is the ONE formatter that turns a products row
    into the retrieval-friendly text chunk. Chroma docs, the LLM's catalog
    context, and eval ground truth all derive from it — the format cannot
    drift between consumers because there is only one copy of it.
  - Exact-code lookups and "show me everything" listings read the TABLE
    (deterministic SQL, always fresh). Only semantic/fuzzy search still
    goes through Chroma — that's the one job embeddings are actually for.
  - sync_chroma() rebuilds a tenant's collection from their active rows,
    and deletes vectors for deactivated products (stale-vector gap closed).

One Rule: every function takes tenant_id and filters on it. There is no
way to read another tenant's products through this module.
"""

from db_client import get_supabase


def product_to_document(p: dict) -> str:
    """One products row -> one small, retrieval-friendly text chunk.

    IDENTICAL output to the format ingest.py used to build straight from
    the CSV — deliberately, so eval_customer_bot.py's live ground-truth
    parsing and the LLM prompt's CATALOG block keep working unchanged.
    Prices are formatted without trailing '.00' noise (NUMERIC(10,2) in
    the DB would otherwise turn 'Rs 450' into 'Rs 450.00' and break the
    eval's parsed expectations).
    """
    price = p["price_inr_per_unit"]
    price_str = f"{price:g}" if isinstance(price, (int, float)) else str(price)
    if price_str.endswith(".00"):
        price_str = price_str[:-3]
    return (
        f"Product {p['product_id']}: {p['name']}. "
        f"Category: {p['category']}. Size: {p['size']}. "
        f"Material: {p['material']}. "
        f"Price: Rs {price_str} {p['unit']}. "
        f"Stock: {p['stock_status'].replace('_', ' ')}. "
        f"Minimum order quantity: {p['min_order_qty']}."
    )


def product_metadata(p: dict) -> dict:
    """Chroma metadata for a products row. Superset of what ingest.py used
    to store (product_id, category, stock_status) so founder_ws.py's
    get_catalog_report keeps working; name + price added because the
    founder overlay wants them anyway and metadata reads are free."""
    return {
        "product_id": p["product_id"],
        "name": p["name"],
        "category": p["category"],
        "stock_status": p["stock_status"],
        "price_inr_per_unit": float(p["price_inr_per_unit"]),
    }


# ── Structured reads (the truth) ─────────────────────────────────────────

def get_products_by_codes(tenant_id: int, codes: list[str]) -> list[dict]:
    """Exact product-code lookup against the table. Deterministic — the
    reason KP005-style bugs can't recur on this path: SQL equality does
    not care that 'KP005' and 'KP001' embed almost identically."""
    if not codes:
        return []
    result = (
        get_supabase()
        .table("products")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .in_("product_id", [c.upper() for c in codes])
        .execute()
    )
    return result.data or []


def get_all_products(tenant_id: int, limit: int = 50) -> list[dict]:
    """Full-catalog listing straight from the table, ordered by product_id
    so 'show me everything' comes out stable, not in vector-insert order.
    Cap kept from main.py's MAX_FULL_CATALOG_DOCS reasoning: a future
    5k-item tenant must not blow the context window."""
    result = (
        get_supabase()
        .table("products")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .order("product_id")
        .limit(limit)
        .execute()
    )
    return result.data or []


# ── Derived-index maintenance ────────────────────────────────────────────

def sync_chroma(tenant_id: int, collection) -> tuple[int, int]:
    """Rebuild a tenant's Chroma collection from their products rows.

    - Active rows: upsert (doc_id = product_id, same as before, so upsert
      genuinely overwrites on price/stock change).
    - Rows now inactive, or vectors whose product_id no longer exists in
      the table at all: deleted from the collection.

    Returns (upserted_count, deleted_count). Called by ingest.py after a
    CSV import, and safe to call any time the table has been edited
    directly (e.g. a price fix from the Supabase editor or, later, the
    Founder Dashboard).
    """
    rows = (
        get_supabase()
        .table("products")
        .select("*")
        .eq("tenant_id", tenant_id)
        .execute()
    ).data or []

    active = [p for p in rows if p["is_active"]]
    active_ids = {p["product_id"] for p in active}

    if active:
        collection.upsert(
            ids=[p["product_id"] for p in active],
            documents=[product_to_document(p) for p in active],
            metadatas=[product_metadata(p) for p in active],
        )

    # Anything in the collection that is not an active product is stale.
    existing = collection.get(include=[])  # ids only
    stale = [i for i in (existing.get("ids") or []) if i not in active_ids]
    if stale:
        collection.delete(ids=stale)

    return len(active), len(stale)
