-- =============================================================================
-- RailYatri — Baseline Database Schema
--
-- This file is the SINGLE SOURCE OF TRUTH for all table definitions.
-- Python application code must NOT contain any CREATE TABLE / ALTER TABLE DDL.
--
-- Schema versioning:
--   This file = baseline only.
--   All future schema evolution must go through app/db/migrations/
--   using Alembic/Flyway-style numbered files.
--
-- Execution: loaded once by DatabaseManager._load_schema_sql() on startup.
--   Uses CREATE TABLE IF NOT EXISTS — idempotent and safe to re-run.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Legacy table cleanup
-- Drop tables from previous schema version that have incompatible structures.
-- ORDER matters: dependents must be dropped before their dependencies.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS train_search_cache CASCADE;
DROP TABLE IF EXISTS tool_executions    CASCADE;
DROP TABLE IF EXISTS interactions       CASCADE;
DROP TABLE IF EXISTS messages           CASCADE;
DROP TABLE IF EXISTS user_pnrs          CASCADE;
DROP TABLE IF EXISTS pnrs               CASCADE;
DROP TABLE IF EXISTS conversations      CASCADE;


-- ---------------------------------------------------------------------------
-- 1. users
--    Authentication, JWT identity, ownership anchor for all user entities.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY,
    email         TEXT        UNIQUE NOT NULL,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
    ON users (email);


-- ---------------------------------------------------------------------------
-- 2. conversations
--    Groups related messages into a chat session.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id         UUID        PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id
    ON conversations (user_id);


-- ---------------------------------------------------------------------------
-- 3. messages
--    Pure conversational history — NO graph execution metadata.
--    Used to reconstruct message_history in GraphState for context.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id              UUID        PRIMARY KEY,
    conversation_id UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages (conversation_id);


-- ---------------------------------------------------------------------------
-- 4. interactions
--    One LangGraph execution trace per user query.
--    High-level observability — NO plan/tool_results JSONB blobs here.
--    Per-tool detail is stored in tool_executions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interactions (
    id              UUID        PRIMARY KEY,
    conversation_id UUID        NOT NULL REFERENCES conversations(id),
    user_id         UUID        NOT NULL,
    query           TEXT        NOT NULL,
    final_response  TEXT,
    is_safe         BOOLEAN,
    top_intent      TEXT,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interactions_conversation_id
    ON interactions (conversation_id);

CREATE INDEX IF NOT EXISTS idx_interactions_user_id
    ON interactions (user_id);


-- ---------------------------------------------------------------------------
-- 5. tool_executions
--    Per-tool execution trace within a graph run.
--    Observability and debugging layer.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool_executions (
    id               UUID        PRIMARY KEY,
    interaction_id   UUID        NOT NULL REFERENCES interactions(id) ON DELETE CASCADE,
    tool_name        TEXT        NOT NULL,
    status           TEXT        NOT NULL CHECK (status IN ('SUCCESS', 'FAILED')),
    error            TEXT,
    execution_time_ms INTEGER,
    input_payload    JSONB,
    output_payload   JSONB,
    created_at       TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_executions_interaction_id
    ON tool_executions (interaction_id);


-- ---------------------------------------------------------------------------
-- 6. pnrs
--    Lightweight cached PNR journey state.
--    External API remains source of truth; this is a read-through cache.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pnrs (
    id                UUID        PRIMARY KEY,
    pnr_number        TEXT        UNIQUE NOT NULL,
    train_number      TEXT,
    journey_date      DATE,
    last_known_status TEXT,
    updated_at        TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pnrs_pnr_number
    ON pnrs (pnr_number);


-- ---------------------------------------------------------------------------
-- 7. user_pnrs
--    Maps a user to a tracked PNR.
--    References pnrs.id (UUID FK, normalized) — NOT raw pnr_number text.
--    Supports future multi-user PNR tracking without duplication.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_pnrs (
    id         UUID        PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pnr_id     UUID        NOT NULL REFERENCES pnrs(id) ON DELETE CASCADE,
    created_at TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_pnrs_user_id_pnr_id_unique
    ON user_pnrs (user_id, pnr_id);

CREATE INDEX IF NOT EXISTS idx_user_pnrs_user_id
    ON user_pnrs (user_id);
