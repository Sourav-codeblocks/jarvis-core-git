"""Jarvis Core — Catalog ingest (CSV -> products table -> derived Chroma).

The pipeline inverted on 2026-07-14. Before: CSV -> Chroma directly, and
the embedded strings WERE the catalog. Now:

    CSV (import format, nothing more)
      -> Supabase `products` (the structured truth: prices, stock, MOQ)
        -> tenant's Chroma collection (derived index, rebuilt from the
           table by catalog_store.sync_chroma — never written from the
           CSV directly)

Consequences that matter:
  - Editing a price in the `products` row + re-running `--sync-only`
    updates the bot. No CSV round-trip required.
  - A product removed from the CSV gets is_active=false AND its vector
    deleted — the stale-vector-lives-forever gap is closed.
  - Re-running on an unchanged CSV is a no-op (upsert on
    (tenant_id, product_id), same doc ids in Chroma).

Usage:
    python ingest.py --csv data/keshri_catalog.csv --tenant keshri-pipes
    python ingest.py --sync-only --tenant keshri-pipes   # table edited directly
"""

import argparse
import csv
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

import catalog_store
from db_client import get_supabase, resolve_tenant

EMBED_MODEL = "all-MiniLM-L6-v2"  # local, free, proven in the HITL lab
CHROMA_DIR = "chroma_db"


def csv_row_to_product(row: dict, tenant_id: int) -> dict:
    """One CSV row -> one products-table row. Types normalized here so the
    table stays clean regardless of how the tenant's CSV was exported."""
    return {
        "tenant_id": tenant_id,
        "product_id": row["product_id"].strip().upper(),
        "name": row["name"].strip(),
        "category": row["category"].strip(),
        "size": row["size"].strip(),
        "material": row["material"].strip(),
        "price_inr_per_unit": float(row["price_inr_per_unit"]),
        "unit": row["unit"].strip(),
        "stock_status": row["stock_status"].strip(),
        "min_order_qty": int(row["min_order_qty"]),
        "is_active": True,
    }


def import_csv(csv_path: Path, tenant_id: int) -> tuple[int, int]:
    """Upsert every CSV row into products; deactivate rows missing from
    the CSV (the CSV is the tenant's full catalog, so absence = delisted).
    Returns (upserted, deactivated)."""
    products = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            products.append(csv_row_to_product(row, tenant_id))

    sb = get_supabase()
    sb.table("products").upsert(
        products, on_conflict="tenant_id,product_id"
    ).execute()

    # Deactivate anything in the table that this CSV no longer contains.
    csv_ids = {p["product_id"] for p in products}
    existing = (
        sb.table("products").select("product_id")
        .eq("tenant_id", tenant_id).eq("is_active", True).execute()
    ).data or []
    gone = [r["product_id"] for r in existing if r["product_id"] not in csv_ids]
    if gone:
        sb.table("products").update({"is_active": False}) \
          .eq("tenant_id", tenant_id).in_("product_id", gone).execute()

    return len(products), len(gone)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Import a catalog CSV into Supabase products, then rebuild "
                    "the tenant's Chroma collection from the table.")
    parser.add_argument("--csv", help="Path to the catalog CSV")
    parser.add_argument("--tenant", required=True,
                        help="Tenant slug (resolves tenant_id + chroma_collection "
                             "via db_client.resolve_tenant — no more passing "
                             "collection names by hand)")
    parser.add_argument("--sync-only", action="store_true",
                        help="Skip the CSV; just rebuild Chroma from the "
                             "products table (use after direct table edits)")
    args = parser.parse_args()

    tenant = resolve_tenant(args.tenant)

    if not args.sync_only:
        if not args.csv:
            raise SystemExit("--csv is required unless --sync-only is set")
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise SystemExit(f"CSV not found: {csv_path}")
        upserted, deactivated = import_csv(csv_path, tenant["id"])
        print(f"products table: {upserted} rows upserted, "
              f"{deactivated} delisted (tenant={tenant['slug']}).")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=tenant["chroma_collection"],
        embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL),
    )
    synced, deleted = catalog_store.sync_chroma(tenant["id"], collection)
    print(f"chroma '{tenant['chroma_collection']}': {synced} vectors synced, "
          f"{deleted} stale removed. Collection now holds {collection.count()}.")


if __name__ == "__main__":
    main()
