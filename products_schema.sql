-- Jarvis Core — products table (structured truth for the catalog)
--
-- Until now the ONLY store for prices/stock was ChromaDB: ingest.py baked
-- each product into an embedded text string, and both the bot's answers
-- and eval_customer_bot.py's ground truth were parsed back OUT of those
-- strings. That inverts the dependency — the derived index was the truth.
--
-- From this migration on:
--   products (this table)  = the truth for prices, stock, MOQ
--   Chroma collection      = a DERIVED index, rebuilt from this table
--                            (see catalog_store.sync_chroma / ingest.py)
--
-- One Rule: tenant_id flows through everything — a product belongs to a
-- tenant, and every lookup filters on it. UNIQUE (tenant_id, product_id)
-- means tenant #2 can also have a "KP001" without collisions.
--
-- Run against the existing Supabase project; only adds a table + trigger,
-- touches nothing already live.

CREATE TABLE products (
    id                 BIGSERIAL PRIMARY KEY,
    tenant_id          BIGINT NOT NULL REFERENCES tenants(id),
    product_id         TEXT NOT NULL,             -- tenant's own code: 'KP001'
    name               TEXT NOT NULL,             -- 'PVC Pipe 4 inch'
    category           TEXT NOT NULL,             -- pipes | fittings | valves | consumables (tenant-defined, not CHECKed)
    size               TEXT,                      -- '4 inch', '12mm x 10m'
    material           TEXT,                      -- 'PVC', 'brass', 'NA'
    price_inr_per_unit NUMERIC(10,2) NOT NULL,
    unit               TEXT NOT NULL,             -- 'per 6m length', 'per piece'
    stock_status       TEXT NOT NULL DEFAULT 'in_stock'
                       CHECK (stock_status IN ('in_stock','low_stock','out_of_stock')),
    min_order_qty      INT NOT NULL DEFAULT 1,
    is_active          BOOLEAN NOT NULL DEFAULT true,
    -- is_active=false means: gone from the tenant's catalog CSV / delisted.
    -- Kept as a row (order history may reference it) but excluded from the
    -- bot's answers AND removed from the Chroma index at sync time. This
    -- closes a gap the pure-Chroma pipeline had: a product deleted from
    -- the CSV lived on as a stale vector forever.
    created_at         TIMESTAMPTZ DEFAULT now(),
    updated_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, product_id)
);

CREATE INDEX products_tenant_active ON products (tenant_id, is_active);

-- updated_at maintained by trigger so ad-hoc price edits from the SQL
-- editor / future Founder Dashboard get timestamped without the writer
-- having to remember to set it.
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER products_touch_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- No INSERT seed here on purpose: rows come from `python ingest.py`,
-- which reads the tenant's catalog CSV, upserts into this table, and then
-- rebuilds the tenant's Chroma collection FROM these rows. The CSV is an
-- import format, not a store.
