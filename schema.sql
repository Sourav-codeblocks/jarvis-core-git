-- Jarvis Core — Phase 0 schema (Postgres / Supabase compatible)
-- Design rule: tenant_id flows through EVERYTHING. No exceptions.

CREATE TABLE tenants (
    id            BIGSERIAL PRIMARY KEY,
    slug          TEXT UNIQUE NOT NULL,          -- 'kesari-pipes'
    display_name  TEXT NOT NULL,                 -- 'Kesari Pipes'
    tier          TEXT NOT NULL DEFAULT 'basic'  -- basic | pro | premium
                  CHECK (tier IN ('basic','pro','premium')),
    branding      JSONB DEFAULT '{}',            -- logo url, greeting, tone
    sop_doc_path  TEXT,                          -- pointer to tenant SOP source
    chroma_collection TEXT NOT NULL,             -- 'kb_kesari_pipes'
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id),
    channel         TEXT NOT NULL,               -- 'telegram' | 'whatsapp'
    channel_user_id TEXT NOT NULL,               -- telegram chat id etc.
    display_name    TEXT,
    reputation      SMALLINT NOT NULL DEFAULT 50 -- 0..100, KPI-driven
                    CHECK (reputation BETWEEN 0 AND 100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, channel, channel_user_id)
);

CREATE TABLE messages (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT NOT NULL REFERENCES tenants(id),
    user_id     BIGINT NOT NULL REFERENCES users(id),
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    text        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_messages_user ON messages (user_id, created_at DESC);

-- THE SWITCHBOX. Founder dashboard is CRUD on this table.
-- Agent client reads enabled rows at session start and mounts only those MCP tools.
CREATE TABLE tenant_tools (
    tenant_id     BIGINT NOT NULL REFERENCES tenants(id),
    tool_key      TEXT NOT NULL,                 -- 'channel.telegram', 'channel.whatsapp',
                                                 -- 'crm.gohighlevel', 'vector.pinecone', 'vector.chroma'
    enabled       BOOLEAN NOT NULL DEFAULT false,
    tier_required TEXT NOT NULL DEFAULT 'basic',
    config        JSONB DEFAULT '{}',            -- non-secret config only
    PRIMARY KEY (tenant_id, tool_key)
);

-- Secrets are NEVER stored raw here — only references to a secret manager / env var name.
CREATE TABLE api_key_refs (
    tenant_id  BIGINT NOT NULL REFERENCES tenants(id),
    provider   TEXT NOT NULL,                    -- 'twilio', 'ghl', 'anthropic'
    secret_ref TEXT NOT NULL,                    -- e.g. env var name or vault path
    PRIMARY KEY (tenant_id, provider)
);

-- Toleration algorithm state. One row per user per day; daily reset = new date row.
CREATE TABLE moderation_state (
    user_id           BIGINT NOT NULL REFERENCES users(id),
    day               DATE NOT NULL DEFAULT CURRENT_DATE,
    offtopic_count    SMALLINT NOT NULL DEFAULT 0,
    hard_ignore_until TIMESTAMPTZ,               -- set on breach; 24h timeout
    PRIMARY KEY (user_id, day)
);

-- Every LLM call writes one row. Founder dashboard reads this for cost/latency per tenant.
CREATE TABLE usage_events (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         BIGINT NOT NULL REFERENCES tenants(id),
    user_id           BIGINT REFERENCES users(id),
    task_type         TEXT NOT NULL,             -- 'intent', 'agent_turn', 'draft', 'research'
    model             TEXT NOT NULL,
    provider          TEXT NOT NULL,             -- 'ollama_local', 'anthropic_api'
    prompt_tokens     INT,
    completion_tokens INT,
    cost_usd          NUMERIC(10,6) DEFAULT 0,   -- 0 for local models
    latency_ms        INT,
    created_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX usage_events_tenant_day ON usage_events (tenant_id, created_at);

-- Seed: tenant #1
INSERT INTO tenants (slug, display_name, tier, chroma_collection)
VALUES ('kesari-pipes', 'Kesari Pipes', 'basic', 'kb_kesari_pipes');

INSERT INTO tenant_tools (tenant_id, tool_key, enabled, tier_required) VALUES
  (1, 'channel.telegram',  true,  'basic'),
  (1, 'channel.whatsapp',  false, 'premium'),
  (1, 'vector.chroma',     true,  'basic'),
  (1, 'crm.gohighlevel',   false, 'pro');
