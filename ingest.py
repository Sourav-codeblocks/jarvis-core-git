"""Jarvis Core — Catalog ingest (Phase 0).

Reads a tenant's catalog CSV, turns each product row into a small text
document, embeds it locally, and stores it in the tenant's own ChromaDB
collection (kb_keshri_pipes — the One Rule applies to knowledge too).

Dedup: each document's ID is the product_id itself. Re-running ingest on
the same file changes nothing; changed rows (price/stock updates) overwrite
the existing vector in place; new rows append. This is the seed of the
future data-cleaning ingest crew.

Usage:
    python ingest.py --csv data/keshri_catalog.csv --collection kb_keshri_pipes
"""

import argparse
import csv
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

EMBED_MODEL = "all-MiniLM-L6-v2"  # local, free, proven in the HITL lab
CHROMA_DIR = "chroma_db"


def row_to_document(row: dict) -> str:
    """One product -> one small, retrieval-friendly text chunk."""
    return (
        f"Product {row['product_id']}: {row['name']}. "
        f"Category: {row['category']}. Size: {row['size']}. "
        f"Material: {row['material']}. "
        f"Price: Rs {row['price_inr_per_unit']} {row['unit']}. "
        f"Stock: {row['stock_status'].replace('_', ' ')}. "
        f"Minimum order quantity: {row['min_order_qty']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a catalog CSV into ChromaDB.")
    parser.add_argument("--csv", required=True, help="Path to the catalog CSV")
    parser.add_argument("--collection", required=True, help="Tenant's collection name")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=args.collection,
        embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL),
    )

    docs, ids, metadatas = [], [], []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doc = row_to_document(row)
            # product_id alone is the ID: same product always maps to the
            # same vector, so upsert genuinely overwrites stale price/stock
            # instead of appending a duplicate.
            doc_id = row["product_id"]
            docs.append(doc)
            ids.append(doc_id)
            metadatas.append({
                "product_id": row["product_id"],
                "category": row["category"],
                "stock_status": row["stock_status"],
            })

    collection.upsert(documents=docs, ids=ids, metadatas=metadatas)
    print(f"Ingested {len(docs)} products into '{args.collection}'. "
          f"Collection now holds {collection.count()} documents.")


if __name__ == "__main__":
    main()