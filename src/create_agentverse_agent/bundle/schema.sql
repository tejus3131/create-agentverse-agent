-- =============================================================================
-- Multipod uAgents Runtime Schema (PostgreSQL)
-- =============================================================================
-- Source of truth for: work queue, load balancing, session locks, idempotency,
-- rate limits, ACL, payments gate, side-effect outbox, conversation history,
-- and agent stores.
--
-- Application pods call SQL functions for coordination (ACID).
--
-- DEPLOYMENT PREREQUISITES:
--   1. Run this migration as a superuser OR a role with BYPASSRLS.
--   2. SECURITY DEFINER functions are owned by that migration role.
--   3. Pods connect via login role agent_pod. Docker Compose creates this role from
--        POSTGRES_USER / POSTGRES_PASSWORD; otherwise create manually and GRANT below.
--   4. Coordination tables have no direct table grants — functions only.
--   5. Policy sync: pods call sync_protocol_acl / sync_protocol_rate_limits at startup.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Schema + roles
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS agent_runtime;

COMMENT ON SCHEMA agent_runtime IS
    'Multipod coordination, queueing, and durable agent state.';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_app') THEN
        CREATE ROLE agent_app NOINHERIT;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA agent_runtime TO agent_app;

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

CREATE TYPE agent_runtime.work_item_status AS ENUM (
    'pending',
    'assigned',
    'processing',
    'completed',
    'failed',
    'rejected'
);

CREATE TYPE agent_runtime.claim_decision AS ENUM (
    'enqueued',
    'already_enqueued',
    'claimed',
    'assigned_to_other',
    'session_busy',
    'worker_at_capacity',
    'worker_draining',
    'worker_not_registered',
    'terminal_completed',
    'terminal_failed',
    'terminal_rejected',
    'not_found'
);

CREATE TYPE agent_runtime.session_lock_decision AS ENUM (
    'acquired',
    'locked_by_other',
    'already_held_by_self'
);

CREATE TYPE agent_runtime.acl_policy AS ENUM ('all', 'none', 'allow', 'deny');

-- ---------------------------------------------------------------------------
-- Workers (pod registry + capacity config)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.workers (
    worker_id          TEXT PRIMARY KEY,
    max_concurrent     INTEGER NOT NULL CHECK (max_concurrent > 0),
    last_heartbeat_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_draining        BOOLEAN NOT NULL DEFAULT FALSE,
    metadata           JSONB NOT NULL DEFAULT '{}'::JSONB
);

COMMENT ON TABLE agent_runtime.workers IS
    'Registered pods. max_concurrent comes from agent config per deployment.';

CREATE INDEX IF NOT EXISTS workers_heartbeat_idx
    ON agent_runtime.workers (last_heartbeat_at);

-- ---------------------------------------------------------------------------
-- Work items (inbox + idempotency + load balancing queue)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.work_items (
    message_id         TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL,
    session_id         TEXT NOT NULL,
    protocol           TEXT NOT NULL CHECK (protocol IN ('chat', 'payment')),
    -- Adding a third protocol requires updating CHECK on protocol_acl and protocol_rate_limits too.
    schema_digest      TEXT,
    status             agent_runtime.work_item_status NOT NULL DEFAULT 'pending',
    assigned_worker_id TEXT REFERENCES agent_runtime.workers (worker_id)
                           ON UPDATE CASCADE ON DELETE RESTRICT,
    payload_json       JSONB NOT NULL DEFAULT '{}'::JSONB,
    error_reason       TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_at        TIMESTAMPTZ,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    expires_at         TIMESTAMPTZ,
    CONSTRAINT terminal_status_requires_completed_at CHECK (
        (status IN ('completed', 'failed', 'rejected') AND completed_at IS NOT NULL)
        OR (status NOT IN ('completed', 'failed', 'rejected'))
    )
);

COMMENT ON TABLE agent_runtime.work_items IS
    'One row per message_id: enqueue, assignment, processing lifecycle.';

CREATE INDEX IF NOT EXISTS work_items_pending_queue_idx
    ON agent_runtime.work_items (created_at)
    WHERE status = 'pending' AND assigned_worker_id IS NULL;

CREATE INDEX IF NOT EXISTS work_items_worker_active_idx
    ON agent_runtime.work_items (assigned_worker_id, status)
    WHERE status IN ('assigned', 'processing');

CREATE INDEX IF NOT EXISTS work_items_session_idx
    ON agent_runtime.work_items (user_id, session_id, created_at);

CREATE INDEX IF NOT EXISTS work_items_session_processing_idx
    ON agent_runtime.work_items (user_id, session_id)
    WHERE status = 'processing';

CREATE INDEX IF NOT EXISTS work_items_expires_idx
    ON agent_runtime.work_items (expires_at)
    WHERE status IN ('assigned', 'processing');

-- ---------------------------------------------------------------------------
-- Session locks (serialize per user/session across pods)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.session_locks (
    user_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    worker_id   TEXT NOT NULL REFERENCES agent_runtime.workers (worker_id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
    message_id  TEXT REFERENCES agent_runtime.work_items (message_id)
                    ON DELETE SET NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, session_id)
);

COMMENT ON TABLE agent_runtime.session_locks IS
    'One active processor per (user_id, session_id).';

CREATE INDEX IF NOT EXISTS session_locks_expires_idx
    ON agent_runtime.session_locks (expires_at);

-- ---------------------------------------------------------------------------
-- Side-effect outbox (external idempotency: payments, replies)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.side_effect_outbox (
    idempotency_key TEXT PRIMARY KEY,
    message_id      TEXT NOT NULL REFERENCES agent_runtime.work_items (message_id)
                        ON DELETE RESTRICT,
    effect_type     TEXT NOT NULL CHECK (
        effect_type IN ('payment_charge', 'chat_reply')
    ),
    payload_json    JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE agent_runtime.side_effect_outbox IS
    'Durable record of external side effects; check before re-firing on retry. '
    'Not cascade-deleted with work_items — purge via purge_side_effect_outbox.';

CREATE INDEX IF NOT EXISTS side_effect_outbox_message_idx
    ON agent_runtime.side_effect_outbox (message_id);

-- ---------------------------------------------------------------------------
-- Protocol policy config (ACL + rate limits)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.protocol_acl (
    protocol    TEXT PRIMARY KEY CHECK (protocol IN ('chat', 'payment')),
    policy      agent_runtime.acl_policy NOT NULL DEFAULT 'all',
    identifiers TEXT[] NOT NULL DEFAULT '{}'::TEXT[]
);

CREATE TABLE agent_runtime.protocol_rate_limits (
    protocol               TEXT PRIMARY KEY CHECK (protocol IN ('chat', 'payment')),
    session_max_requests   INTEGER NOT NULL CHECK (session_max_requests > 0),
    session_window_seconds INTEGER NOT NULL CHECK (session_window_seconds > 0),
    user_max_requests      INTEGER NOT NULL CHECK (user_max_requests > 0),
    user_window_seconds    INTEGER NOT NULL CHECK (user_window_seconds > 0)
);

-- ---------------------------------------------------------------------------
-- Rate limit counters (Postgres-backed sliding window)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.session_rate_counters (
    user_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    protocol    TEXT NOT NULL,
    timestamps  TIMESTAMPTZ[] NOT NULL DEFAULT '{}'::TIMESTAMPTZ[],
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, session_id, protocol)
);

CREATE TABLE agent_runtime.user_rate_counters (
    user_id     TEXT NOT NULL,
    protocol    TEXT NOT NULL,
    timestamps  TIMESTAMPTZ[] NOT NULL DEFAULT '{}'::TIMESTAMPTZ[],
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, protocol)
);

-- ---------------------------------------------------------------------------
-- Payment gate + conversation + stores (durable agent state)
-- ---------------------------------------------------------------------------

CREATE TABLE agent_runtime.active_payment_requests (
    user_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    value      JSONB NOT NULL,
    PRIMARY KEY (user_id, session_id)
);

CREATE INDEX IF NOT EXISTS active_payment_requests_value_gin_idx
    ON agent_runtime.active_payment_requests USING GIN (value);

CREATE SEQUENCE IF NOT EXISTS agent_runtime.conversation_history_id_seq;

CREATE TABLE agent_runtime.conversation_history (
    id           BIGINT NOT NULL DEFAULT nextval('agent_runtime.conversation_history_id_seq'),
    actor_type   TEXT NOT NULL,
    actor_id     TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL,
    message_type TEXT NOT NULL,
    content_json JSONB NOT NULL,
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS conversation_actor_idx
    ON agent_runtime.conversation_history (actor_type, actor_id, session_id);

CREATE INDEX IF NOT EXISTS conversation_session_idx
    ON agent_runtime.conversation_history (session_id, timestamp);

CREATE INDEX IF NOT EXISTS conversation_user_session_idx
    ON agent_runtime.conversation_history (actor_id, session_id, timestamp);

CREATE TABLE agent_runtime.persistent_store (
    user_id TEXT NOT NULL PRIMARY KEY,
    value   JSONB NOT NULL
);

CREATE TABLE agent_runtime.session_store (
    user_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    value      JSONB NOT NULL,
    PRIMARY KEY (user_id, session_id)
);

CREATE TABLE agent_runtime.registered_with_agentverse (
    user_id TEXT NOT NULL PRIMARY KEY,
    value   JSONB NOT NULL
);

COMMENT ON TABLE agent_runtime.registered_with_agentverse IS
    'Agentverse registration flag; same RLS model as other state tables.';

-- ---------------------------------------------------------------------------
-- Default policy rows
-- ---------------------------------------------------------------------------

INSERT INTO agent_runtime.protocol_acl (protocol, policy, identifiers)
VALUES
    ('chat', 'all', '{}'),
    ('payment', 'all', '{}')
ON CONFLICT (protocol) DO NOTHING;

INSERT INTO agent_runtime.protocol_rate_limits (
    protocol,
    session_max_requests,
    session_window_seconds,
    user_max_requests,
    user_window_seconds
)
VALUES
    ('chat', 10, 60, 50, 60),
    ('payment', 10, 60, 50, 60)
ON CONFLICT (protocol) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Helper: active work count for a worker
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.worker_active_count(p_worker_id TEXT)
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM agent_runtime.work_items
    WHERE assigned_worker_id = p_worker_id
      AND status IN ('assigned', 'processing');
$$;

-- ---------------------------------------------------------------------------
-- heartbeat_worker
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.heartbeat_worker(
    p_worker_id        TEXT,
    p_max_concurrent   INTEGER DEFAULT NULL,
    p_is_draining      BOOLEAN DEFAULT FALSE,
    p_metadata         JSONB DEFAULT '{}'::JSONB
)
RETURNS agent_runtime.workers
LANGUAGE plpgsql
AS $$
DECLARE
    v_worker agent_runtime.workers;
BEGIN
    INSERT INTO agent_runtime.workers (
        worker_id,
        max_concurrent,
        last_heartbeat_at,
        is_draining,
        metadata
    )
    VALUES (
        p_worker_id,
        COALESCE(p_max_concurrent, 1),
        NOW(),
        p_is_draining,
        COALESCE(p_metadata, '{}'::JSONB)
    )
    ON CONFLICT (worker_id) DO UPDATE
    SET last_heartbeat_at = NOW(),
        max_concurrent = COALESCE(p_max_concurrent, agent_runtime.workers.max_concurrent),
        is_draining = p_is_draining,
        metadata = agent_runtime.workers.metadata || COALESCE(p_metadata, '{}'::JSONB)
    RETURNING * INTO v_worker;

    RETURN v_worker;
END;
$$;

-- ---------------------------------------------------------------------------
-- reclaim_stale_work (background only — not called on enqueue/claim)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.reclaim_stale_work(
    p_assignment_grace_seconds         INTEGER DEFAULT 0,
    p_lock_grace_seconds               INTEGER DEFAULT 0,
    p_worker_heartbeat_stale_seconds   INTEGER DEFAULT 45
)
RETURNS TABLE (
    reclaimed_assigned    INTEGER,
    reclaimed_processing  INTEGER,
    reclaimed_session_locks INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_assigned   INTEGER;
    v_processing INTEGER;
    v_lock       INTEGER;
BEGIN
    -- assigned: short pre-handler lease expires
    UPDATE agent_runtime.work_items
    SET status = 'pending',
        assigned_worker_id = NULL,
        assigned_at = NULL,
        started_at = NULL,
        expires_at = NULL
    WHERE status = 'assigned'
      AND expires_at IS NOT NULL
      AND expires_at < NOW() - (p_assignment_grace_seconds * INTERVAL '1 second');

    GET DIAGNOSTICS v_assigned = ROW_COUNT;

    -- processing: reclaim only when worker heartbeat is stale (not expires_at)
    UPDATE agent_runtime.work_items AS wi
    SET status = 'pending',
        assigned_worker_id = NULL,
        assigned_at = NULL,
        started_at = NULL,
        expires_at = NULL
    WHERE wi.status = 'processing'
      AND wi.assigned_worker_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.workers AS w
          WHERE w.worker_id = wi.assigned_worker_id
            AND w.last_heartbeat_at > NOW()
                - (p_worker_heartbeat_stale_seconds * INTERVAL '1 second')
      );

    GET DIAGNOSTICS v_processing = ROW_COUNT;

    -- Orphaned processing rows (e.g. if worker row was removed out-of-band)
    UPDATE agent_runtime.work_items
    SET status = 'pending',
        assigned_worker_id = NULL,
        assigned_at = NULL,
        started_at = NULL,
        expires_at = NULL
    WHERE status = 'processing'
      AND assigned_worker_id IS NULL;

    DELETE FROM agent_runtime.session_locks AS sl
    WHERE sl.expires_at < NOW() - (p_lock_grace_seconds * INTERVAL '1 second')
       OR NOT EXISTS (
           SELECT 1
           FROM agent_runtime.workers AS w
           WHERE w.worker_id = sl.worker_id
             AND w.last_heartbeat_at > NOW()
                 - (p_worker_heartbeat_stale_seconds * INTERVAL '1 second')
       );

    GET DIAGNOSTICS v_lock = ROW_COUNT;

    reclaimed_assigned := v_assigned;
    reclaimed_processing := v_processing;
    reclaimed_session_locks := v_lock;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- enqueue_work_item (idempotent inbox insert)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.enqueue_work_item(
    p_message_id    TEXT,
    p_user_id       TEXT,
    p_session_id    TEXT,
    p_protocol      TEXT,
    p_payload_json  JSONB DEFAULT '{}'::JSONB,
    p_schema_digest TEXT DEFAULT NULL
)
RETURNS TABLE (
    decision agent_runtime.claim_decision,
    work_item agent_runtime.work_items
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_item agent_runtime.work_items;
BEGIN
    INSERT INTO agent_runtime.work_items (
        message_id,
        user_id,
        session_id,
        protocol,
        schema_digest,
        payload_json,
        status
    )
    VALUES (
        p_message_id,
        p_user_id,
        p_session_id,
        p_protocol,
        p_schema_digest,
        COALESCE(p_payload_json, '{}'::JSONB),
        'pending'
    )
    ON CONFLICT (message_id) DO NOTHING
    RETURNING * INTO v_item;

    IF FOUND THEN
        decision := 'enqueued';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT * INTO v_item
    FROM agent_runtime.work_items
    WHERE message_id = p_message_id;

    decision := 'already_enqueued';
    work_item := v_item;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- claim_work_item (atomic assignment + capacity check, worker row locked)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.claim_work_item(
    p_worker_id              TEXT,
    p_message_id             TEXT,
    p_assignment_ttl_seconds INTEGER DEFAULT 90
)
RETURNS TABLE (
    decision agent_runtime.claim_decision,
    work_item agent_runtime.work_items
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_worker agent_runtime.workers;
    v_item   agent_runtime.work_items;
    v_active INTEGER;
BEGIN
    SELECT * INTO v_worker
    FROM agent_runtime.workers
    WHERE worker_id = p_worker_id
    FOR UPDATE;

    IF NOT FOUND THEN
        decision := 'worker_not_registered';
        work_item := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_worker.is_draining THEN
        decision := 'worker_draining';
        work_item := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT * INTO v_item
    FROM agent_runtime.work_items
    WHERE message_id = p_message_id;

    IF NOT FOUND THEN
        decision := 'not_found';
        work_item := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.status = 'completed' THEN
        decision := 'terminal_completed';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.status = 'failed' THEN
        decision := 'terminal_failed';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.status = 'rejected' THEN
        decision := 'terminal_rejected';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.assigned_worker_id IS NOT NULL
       AND v_item.assigned_worker_id <> p_worker_id
       AND v_item.status IN ('assigned', 'processing') THEN
        decision := 'assigned_to_other';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.assigned_worker_id = p_worker_id
       AND v_item.status IN ('assigned', 'processing') THEN
        decision := 'claimed';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM agent_runtime.work_items AS wi2
        WHERE wi2.user_id = v_item.user_id
          AND wi2.session_id = v_item.session_id
          AND wi2.message_id <> p_message_id
          AND wi2.assigned_worker_id = p_worker_id
          AND wi2.status IN ('assigned', 'processing')
    ) THEN
        decision := 'session_busy';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM agent_runtime.work_items AS wi_older
        WHERE wi_older.user_id = v_item.user_id
          AND wi_older.session_id = v_item.session_id
          AND wi_older.message_id <> p_message_id
          AND wi_older.status = 'pending'
          AND wi_older.assigned_worker_id IS NULL
          AND wi_older.created_at < v_item.created_at
    ) THEN
        decision := 'session_busy';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    v_active := agent_runtime.worker_active_count(p_worker_id);
    IF v_active >= v_worker.max_concurrent THEN
        decision := 'worker_at_capacity';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    UPDATE agent_runtime.work_items AS wi
    SET status = 'assigned',
        assigned_worker_id = p_worker_id,
        assigned_at = NOW(),
        expires_at = NOW() + (p_assignment_ttl_seconds * INTERVAL '1 second')
    WHERE wi.message_id = p_message_id
      AND wi.status = 'pending'
      AND wi.assigned_worker_id IS NULL
    RETURNING * INTO v_item;

    IF FOUND THEN
        decision := 'claimed';
        work_item := v_item;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT * INTO v_item
    FROM agent_runtime.work_items
    WHERE message_id = p_message_id;

    IF v_item.assigned_worker_id IS NOT NULL
       AND v_item.assigned_worker_id <> p_worker_id THEN
        decision := 'assigned_to_other';
    ELSE
        decision := 'worker_at_capacity';
    END IF;

    work_item := v_item;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- claim_next_pending_work (session-aware drain queue)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.claim_next_pending_work(
    p_worker_id              TEXT,
    p_assignment_ttl_seconds INTEGER DEFAULT 90
)
RETURNS TABLE (
    decision agent_runtime.claim_decision,
    work_item agent_runtime.work_items
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_message_id TEXT;
BEGIN
    SELECT wi.message_id
    INTO v_message_id
    FROM agent_runtime.work_items AS wi
    WHERE wi.status = 'pending'
      AND wi.assigned_worker_id IS NULL
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.session_locks AS sl
          WHERE sl.user_id = wi.user_id
            AND sl.session_id = wi.session_id
            AND sl.expires_at >= NOW()
      )
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.work_items AS wi2
          WHERE wi2.user_id = wi.user_id
            AND wi2.session_id = wi.session_id
            AND wi2.status = 'processing'
            AND wi2.message_id <> wi.message_id
      )
    ORDER BY wi.created_at
    FOR UPDATE OF wi SKIP LOCKED
    LIMIT 1;

    IF v_message_id IS NULL THEN
        RETURN QUERY
        SELECT
            'not_found'::agent_runtime.claim_decision,
            NULL::agent_runtime.work_items;
        RETURN;
    END IF;

    RETURN QUERY
    SELECT c.decision, c.work_item
    FROM agent_runtime.claim_work_item(
        p_worker_id,
        v_message_id,
        p_assignment_ttl_seconds
    ) AS c;
END;
$$;

-- ---------------------------------------------------------------------------
-- revert_work_assignment (assigned only — not processing)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.revert_work_assignment(
    p_worker_id  TEXT,
    p_message_id TEXT
)
RETURNS agent_runtime.work_items
LANGUAGE plpgsql
AS $$
DECLARE
    v_item agent_runtime.work_items;
BEGIN
    UPDATE agent_runtime.work_items
    SET status = 'pending',
        assigned_worker_id = NULL,
        assigned_at = NULL,
        started_at = NULL,
        expires_at = NULL
    WHERE message_id = p_message_id
      AND assigned_worker_id = p_worker_id
      AND status = 'assigned'
    RETURNING * INTO v_item;

    RETURN v_item;
END;
$$;

-- ---------------------------------------------------------------------------
-- acquire_session_lock
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.acquire_session_lock(
    p_worker_id   TEXT,
    p_user_id     TEXT,
    p_session_id  TEXT,
    p_message_id  TEXT,
    p_ttl_seconds INTEGER DEFAULT 180
)
RETURNS TABLE (
    decision agent_runtime.session_lock_decision,
    holder   TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_holder          TEXT;
    v_existing_holder TEXT;
    v_locked_message  TEXT;
    v_locked_status   agent_runtime.work_item_status;
BEGIN
    DELETE FROM agent_runtime.session_locks
    WHERE user_id = p_user_id
      AND session_id = p_session_id
      AND expires_at < NOW();

    SELECT sl.worker_id, sl.message_id
    INTO v_existing_holder, v_locked_message
    FROM agent_runtime.session_locks AS sl
    WHERE sl.user_id = p_user_id
      AND sl.session_id = p_session_id
      AND sl.expires_at >= NOW();

    IF v_existing_holder = p_worker_id THEN
        IF v_locked_message IS NOT NULL
           AND v_locked_message <> p_message_id THEN
            SELECT wi.status
            INTO v_locked_status
            FROM agent_runtime.work_items AS wi
            WHERE wi.message_id = v_locked_message;

            IF v_locked_status IN ('assigned', 'processing') THEN
                decision := 'locked_by_other';
                holder := p_worker_id;
                RETURN NEXT;
                RETURN;
            END IF;
        END IF;

        UPDATE agent_runtime.session_locks
        SET message_id = p_message_id,
            acquired_at = NOW(),
            expires_at = NOW() + (p_ttl_seconds * INTERVAL '1 second')
        WHERE user_id = p_user_id
          AND session_id = p_session_id
          AND worker_id = p_worker_id;

        decision := 'already_held_by_self';
        holder := p_worker_id;
        RETURN NEXT;
        RETURN;
    END IF;

    INSERT INTO agent_runtime.session_locks (
        user_id,
        session_id,
        worker_id,
        message_id,
        expires_at
    )
    VALUES (
        p_user_id,
        p_session_id,
        p_worker_id,
        p_message_id,
        NOW() + (p_ttl_seconds * INTERVAL '1 second')
    )
    ON CONFLICT (user_id, session_id) DO UPDATE
    SET worker_id = EXCLUDED.worker_id,
        message_id = EXCLUDED.message_id,
        acquired_at = NOW(),
        expires_at = EXCLUDED.expires_at
    WHERE agent_runtime.session_locks.expires_at < NOW()
       OR agent_runtime.session_locks.worker_id = EXCLUDED.worker_id
    RETURNING worker_id INTO v_holder;

    IF v_holder = p_worker_id THEN
        decision := 'acquired';
        holder := v_holder;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT sl.worker_id INTO v_holder
    FROM agent_runtime.session_locks AS sl
    WHERE sl.user_id = p_user_id
      AND sl.session_id = p_session_id
      AND sl.expires_at >= NOW();

    decision := 'locked_by_other';
    holder := v_holder;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- refresh_session_lock (long-running handlers)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.refresh_session_lock(
    p_worker_id   TEXT,
    p_user_id     TEXT,
    p_session_id  TEXT,
    p_ttl_seconds INTEGER DEFAULT 180
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE agent_runtime.session_locks
    SET expires_at = NOW() + (p_ttl_seconds * INTERVAL '1 second')
    WHERE user_id = p_user_id
      AND session_id = p_session_id
      AND worker_id = p_worker_id
      AND expires_at >= NOW();

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated = 1;
END;
$$;

-- ---------------------------------------------------------------------------
-- refresh_work_item_lease (metrics / optional extension during long handlers)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.refresh_work_item_lease(
    p_worker_id   TEXT,
    p_message_id  TEXT,
    p_ttl_seconds INTEGER DEFAULT 180
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE agent_runtime.work_items
    SET expires_at = NOW() + (p_ttl_seconds * INTERVAL '1 second')
    WHERE message_id = p_message_id
      AND assigned_worker_id = p_worker_id
      AND status = 'processing';

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated = 1;
END;
$$;

-- ---------------------------------------------------------------------------
-- release_session_lock
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.release_session_lock(
    p_worker_id  TEXT,
    p_user_id    TEXT,
    p_session_id TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM agent_runtime.session_locks
    WHERE user_id = p_user_id
      AND session_id = p_session_id
      AND worker_id = p_worker_id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted = 1;
END;
$$;

-- ---------------------------------------------------------------------------
-- start_processing_work
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.start_processing_work(
    p_worker_id              TEXT,
    p_message_id             TEXT,
    p_processing_ttl_seconds INTEGER DEFAULT 180
)
RETURNS agent_runtime.work_items
LANGUAGE plpgsql
AS $$
DECLARE
    v_item agent_runtime.work_items;
BEGIN
    UPDATE agent_runtime.work_items
    SET status = 'processing',
        started_at = NOW(),
        expires_at = NOW() + (p_processing_ttl_seconds * INTERVAL '1 second')
    WHERE message_id = p_message_id
      AND assigned_worker_id = p_worker_id
      AND status = 'assigned'
    RETURNING * INTO v_item;

    RETURN v_item;
END;
$$;

-- ---------------------------------------------------------------------------
-- complete_work_item
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.complete_work_item(
    p_worker_id    TEXT,
    p_message_id   TEXT,
    p_status       agent_runtime.work_item_status,
    p_error_reason TEXT DEFAULT NULL
)
RETURNS agent_runtime.work_items
LANGUAGE plpgsql
AS $$
DECLARE
    v_item agent_runtime.work_items;
BEGIN
    IF p_status NOT IN ('completed', 'failed', 'rejected') THEN
        RAISE EXCEPTION 'complete_work_item requires a terminal status';
    END IF;

    UPDATE agent_runtime.work_items
    SET status = p_status,
        error_reason = p_error_reason,
        completed_at = NOW(),
        expires_at = NULL,
        assigned_worker_id = NULL
    WHERE message_id = p_message_id
      AND assigned_worker_id = p_worker_id
      AND status IN ('assigned', 'processing')
    RETURNING * INTO v_item;

    RETURN v_item;
END;
$$;

-- ---------------------------------------------------------------------------
-- Side-effect outbox
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.has_side_effect(p_idempotency_key TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM agent_runtime.side_effect_outbox
        WHERE idempotency_key = p_idempotency_key
    );
$$;

CREATE OR REPLACE FUNCTION agent_runtime.record_side_effect(
    p_message_id       TEXT,
    p_effect_type      TEXT,
    p_idempotency_key  TEXT,
    p_payload_json     JSONB DEFAULT '{}'::JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_inserted TEXT;
BEGIN
    INSERT INTO agent_runtime.side_effect_outbox (
        idempotency_key,
        message_id,
        effect_type,
        payload_json
    )
    VALUES (
        p_idempotency_key,
        p_message_id,
        p_effect_type,
        COALESCE(p_payload_json, '{}'::JSONB)
    )
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING idempotency_key INTO v_inserted;

    RETURN v_inserted IS NOT NULL;
END;
$$;

-- ---------------------------------------------------------------------------
-- check_acl
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.check_acl(
    p_protocol TEXT,
    p_sender   TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_policy agent_runtime.acl_policy;
    v_ids    TEXT[];
BEGIN
    SELECT policy, identifiers
    INTO v_policy, v_ids
    FROM agent_runtime.protocol_acl
    WHERE protocol = p_protocol;

    IF NOT FOUND THEN
        RETURN TRUE;
    END IF;

    CASE v_policy
        WHEN 'all' THEN RETURN TRUE;
        WHEN 'none' THEN RETURN FALSE;
        WHEN 'allow' THEN RETURN p_sender = ANY (v_ids);
        WHEN 'deny' THEN RETURN NOT (p_sender = ANY (v_ids));
        ELSE RETURN FALSE;
    END CASE;
END;
$$;

-- ---------------------------------------------------------------------------
-- check_payment_gate
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.check_payment_gate(
    p_user_id    TEXT,
    p_session_id TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT NOT EXISTS (
        SELECT 1
        FROM agent_runtime.active_payment_requests
        WHERE user_id = p_user_id
          AND session_id = p_session_id
    );
$$;

-- ---------------------------------------------------------------------------
-- check_and_record_rate_limit
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.check_and_record_rate_limit(
    p_user_id    TEXT,
    p_session_id TEXT,
    p_protocol   TEXT
)
RETURNS TABLE (
    allowed          BOOLEAN,
    limit_type       TEXT,
    cooldown_seconds INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cfg agent_runtime.protocol_rate_limits;
    v_now TIMESTAMPTZ := NOW();
    v_session_ts TIMESTAMPTZ[];
    v_user_ts TIMESTAMPTZ[];
    v_cutoff_session TIMESTAMPTZ;
    v_cutoff_user TIMESTAMPTZ;
    v_oldest TIMESTAMPTZ;
BEGIN
    SELECT * INTO v_cfg
    FROM agent_runtime.protocol_rate_limits
    WHERE protocol = p_protocol;

    IF NOT FOUND THEN
        allowed := TRUE;
        limit_type := 'none';
        cooldown_seconds := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    v_cutoff_session := v_now - (v_cfg.session_window_seconds * INTERVAL '1 second');
    v_cutoff_user := v_now - (v_cfg.user_window_seconds * INTERVAL '1 second');

    INSERT INTO agent_runtime.session_rate_counters (user_id, session_id, protocol, timestamps)
    VALUES (p_user_id, p_session_id, p_protocol, '{}'::TIMESTAMPTZ[])
    ON CONFLICT (user_id, session_id, protocol) DO NOTHING;

    INSERT INTO agent_runtime.user_rate_counters (user_id, protocol, timestamps)
    VALUES (p_user_id, p_protocol, '{}'::TIMESTAMPTZ[])
    ON CONFLICT (user_id, protocol) DO NOTHING;

    SELECT timestamps INTO v_session_ts
    FROM agent_runtime.session_rate_counters
    WHERE user_id = p_user_id
      AND session_id = p_session_id
      AND protocol = p_protocol
    FOR UPDATE;

    SELECT timestamps INTO v_user_ts
    FROM agent_runtime.user_rate_counters
    WHERE user_id = p_user_id
      AND protocol = p_protocol
    FOR UPDATE;

    v_session_ts := ARRAY(
        SELECT ts FROM unnest(v_session_ts) AS ts
        WHERE ts >= v_cutoff_session
        ORDER BY ts
    );

    IF COALESCE(array_length(v_session_ts, 1), 0) >= v_cfg.session_max_requests THEN
        SELECT MIN(ts) INTO v_oldest FROM unnest(v_session_ts) AS ts;
        allowed := FALSE;
        limit_type := 'session';
        cooldown_seconds := GREATEST(
            0,
            EXTRACT(EPOCH FROM (v_oldest + (v_cfg.session_window_seconds * INTERVAL '1 second') - v_now))::INTEGER
        );
        RETURN NEXT;
        RETURN;
    END IF;

    v_user_ts := ARRAY(
        SELECT ts FROM unnest(v_user_ts) AS ts
        WHERE ts >= v_cutoff_user
        ORDER BY ts
    );

    IF COALESCE(array_length(v_user_ts, 1), 0) >= v_cfg.user_max_requests THEN
        SELECT MIN(ts) INTO v_oldest FROM unnest(v_user_ts) AS ts;
        allowed := FALSE;
        limit_type := 'user';
        cooldown_seconds := GREATEST(
            0,
            EXTRACT(EPOCH FROM (v_oldest + (v_cfg.user_window_seconds * INTERVAL '1 second') - v_now))::INTEGER
        );
        RETURN NEXT;
        RETURN;
    END IF;

    v_session_ts := v_session_ts || v_now;
    v_user_ts := v_user_ts || v_now;

    UPDATE agent_runtime.session_rate_counters
    SET timestamps = v_session_ts,
        updated_at = v_now
    WHERE user_id = p_user_id
      AND session_id = p_session_id
      AND protocol = p_protocol;

    UPDATE agent_runtime.user_rate_counters
    SET timestamps = v_user_ts,
        updated_at = v_now
    WHERE user_id = p_user_id
      AND protocol = p_protocol;

    allowed := TRUE;
    limit_type := 'none';
    cooldown_seconds := 0;
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- Bootstrap: sync protocol policy from app config (pods call at startup)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.sync_protocol_acl(
    p_protocol    TEXT,
    p_policy      TEXT,
    p_identifiers TEXT[] DEFAULT '{}'::TEXT[]
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_protocol NOT IN ('chat', 'payment') THEN
        RAISE EXCEPTION 'invalid protocol: %', p_protocol;
    END IF;

    IF p_policy NOT IN ('all', 'none', 'allow', 'deny') THEN
        RAISE EXCEPTION 'invalid acl policy: %', p_policy;
    END IF;

    INSERT INTO agent_runtime.protocol_acl (protocol, policy, identifiers)
    VALUES (
        p_protocol,
        p_policy::agent_runtime.acl_policy,
        COALESCE(p_identifiers, '{}'::TEXT[])
    )
    ON CONFLICT (protocol) DO UPDATE
    SET policy = EXCLUDED.policy,
        identifiers = EXCLUDED.identifiers;
END;
$$;

CREATE OR REPLACE FUNCTION agent_runtime.sync_protocol_rate_limits(
    p_protocol               TEXT,
    p_session_max_requests   INTEGER,
    p_session_window_seconds INTEGER,
    p_user_max_requests      INTEGER,
    p_user_window_seconds    INTEGER
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_protocol NOT IN ('chat', 'payment') THEN
        RAISE EXCEPTION 'invalid protocol: %', p_protocol;
    END IF;

    IF p_session_max_requests <= 0
       OR p_session_window_seconds <= 0
       OR p_user_max_requests <= 0
       OR p_user_window_seconds <= 0 THEN
        RAISE EXCEPTION 'rate limit values must be positive';
    END IF;

    INSERT INTO agent_runtime.protocol_rate_limits (
        protocol,
        session_max_requests,
        session_window_seconds,
        user_max_requests,
        user_window_seconds
    )
    VALUES (
        p_protocol,
        p_session_max_requests,
        p_session_window_seconds,
        p_user_max_requests,
        p_user_window_seconds
    )
    ON CONFLICT (protocol) DO UPDATE
    SET session_max_requests = EXCLUDED.session_max_requests,
        session_window_seconds = EXCLUDED.session_window_seconds,
        user_max_requests = EXCLUDED.user_max_requests,
        user_window_seconds = EXCLUDED.user_window_seconds;
END;
$$;

-- ---------------------------------------------------------------------------
-- Retention maintenance
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.purge_terminal_work_items(
    p_chat_older_than_days    INTEGER DEFAULT 7,
    p_payment_older_than_days INTEGER DEFAULT 365
)
RETURNS TABLE (
    chat_outbox_deleted    INTEGER,
    chat_items_deleted     INTEGER,
    payment_outbox_deleted INTEGER,
    payment_items_deleted  INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_chat_outbox    INTEGER;
    v_chat_items     INTEGER;
    v_payment_outbox INTEGER;
    v_payment_items  INTEGER;
    v_chat_cutoff    TIMESTAMPTZ;
    v_payment_cutoff TIMESTAMPTZ;
BEGIN
    v_chat_cutoff := NOW() - (p_chat_older_than_days * INTERVAL '1 day');
    v_payment_cutoff := NOW() - (p_payment_older_than_days * INTERVAL '1 day');

    DELETE FROM agent_runtime.side_effect_outbox AS o
    WHERE o.effect_type = 'chat_reply'
      AND o.created_at < v_chat_cutoff
      AND EXISTS (
          SELECT 1
          FROM agent_runtime.work_items AS wi
          WHERE wi.message_id = o.message_id
            AND wi.protocol = 'chat'
            AND wi.status IN ('completed', 'failed', 'rejected')
            AND wi.completed_at < v_chat_cutoff
      );

    GET DIAGNOSTICS v_chat_outbox = ROW_COUNT;

    DELETE FROM agent_runtime.work_items
    WHERE protocol = 'chat'
      AND status IN ('completed', 'failed', 'rejected')
      AND completed_at < v_chat_cutoff
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.side_effect_outbox AS o
          WHERE o.message_id = work_items.message_id
      );

    GET DIAGNOSTICS v_chat_items = ROW_COUNT;

    DELETE FROM agent_runtime.side_effect_outbox AS o
    WHERE o.effect_type = 'payment_charge'
      AND o.created_at < v_payment_cutoff
      AND EXISTS (
          SELECT 1
          FROM agent_runtime.work_items AS wi
          WHERE wi.message_id = o.message_id
            AND wi.protocol = 'payment'
            AND wi.status IN ('completed', 'failed', 'rejected')
            AND wi.completed_at < v_payment_cutoff
      );

    GET DIAGNOSTICS v_payment_outbox = ROW_COUNT;

    DELETE FROM agent_runtime.work_items
    WHERE protocol = 'payment'
      AND status IN ('completed', 'failed', 'rejected')
      AND completed_at < v_payment_cutoff
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.side_effect_outbox AS o
          WHERE o.message_id = work_items.message_id
      );

    GET DIAGNOSTICS v_payment_items = ROW_COUNT;

    chat_outbox_deleted := v_chat_outbox;
    chat_items_deleted := v_chat_items;
    payment_outbox_deleted := v_payment_outbox;
    payment_items_deleted := v_payment_items;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION agent_runtime.purge_side_effect_outbox(
    p_older_than_days INTEGER DEFAULT 365
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM agent_runtime.side_effect_outbox
    WHERE created_at < NOW() - (p_older_than_days * INTERVAL '1 day');

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION agent_runtime.purge_idle_rate_counters(
    p_older_than_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    session_counters_deleted INTEGER,
    user_counters_deleted INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_session INTEGER;
    v_user INTEGER;
    v_cutoff TIMESTAMPTZ;
BEGIN
    v_cutoff := NOW() - (p_older_than_days * INTERVAL '1 day');

    DELETE FROM agent_runtime.session_rate_counters
    WHERE updated_at < v_cutoff;

    GET DIAGNOSTICS v_session = ROW_COUNT;

    DELETE FROM agent_runtime.user_rate_counters
    WHERE updated_at < v_cutoff;

    GET DIAGNOSTICS v_user = ROW_COUNT;

    session_counters_deleted := v_session;
    user_counters_deleted := v_user;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION agent_runtime.purge_stale_workers(
    p_heartbeat_stale_seconds INTEGER DEFAULT 86400
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM agent_runtime.workers AS w
    WHERE w.last_heartbeat_at < NOW() - (p_heartbeat_stale_seconds * INTERVAL '1 second')
      AND w.is_draining = TRUE
      AND NOT EXISTS (
          SELECT 1
          FROM agent_runtime.work_items AS wi
          WHERE wi.assigned_worker_id = w.worker_id
            AND wi.status IN ('assigned', 'processing')
      );

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

-- ---------------------------------------------------------------------------
-- process_inbound_message (orchestrator)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.process_inbound_message(
    p_worker_id                  TEXT,
    p_message_id                 TEXT,
    p_user_id                    TEXT,
    p_session_id                 TEXT,
    p_protocol                   TEXT,
    p_payload_json               JSONB DEFAULT '{}'::JSONB,
    p_schema_digest              TEXT DEFAULT NULL,
    p_assignment_ttl_seconds       INTEGER DEFAULT 90,
    p_processing_ttl_seconds       INTEGER DEFAULT 180,
    p_session_lock_ttl_seconds     INTEGER DEFAULT 180
)
RETURNS TABLE (
    stage    TEXT,
    decision TEXT,
    detail   JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_enqueue_decision agent_runtime.claim_decision;
    v_claim_decision   agent_runtime.claim_decision;
    v_enqueue_row      RECORD;
    v_claim_row        RECORD;
    v_item             agent_runtime.work_items;
    v_lock_decision    agent_runtime.session_lock_decision;
    v_lock_holder      TEXT;
    v_acl_ok           BOOLEAN;
    v_payment_ok       BOOLEAN;
    v_rate_allowed     BOOLEAN;
    v_rate_type        TEXT;
    v_rate_cooldown    INTEGER;
BEGIN
    SELECT *
    INTO v_enqueue_row
    FROM agent_runtime.enqueue_work_item(
        p_message_id,
        p_user_id,
        p_session_id,
        p_protocol,
        p_payload_json,
        p_schema_digest
    ) AS e;

    v_enqueue_decision := v_enqueue_row.decision;
    v_item := v_enqueue_row.work_item;

    IF v_item.status IN ('completed', 'failed', 'rejected') THEN
        stage := 'enqueue';
        decision := v_item.status::TEXT;
        detail := jsonb_build_object('message_id', p_message_id);
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT *
    INTO v_claim_row
    FROM agent_runtime.claim_work_item(
        p_worker_id,
        p_message_id,
        p_assignment_ttl_seconds
    ) AS c;

    v_claim_decision := v_claim_row.decision;
    v_item := v_claim_row.work_item;

    IF v_claim_decision IN (
        'worker_at_capacity',
        'worker_draining',
        'session_busy',
        'assigned_to_other',
        'worker_not_registered'
    ) THEN
        stage := 'claim';
        decision := v_claim_decision::TEXT;
        detail := jsonb_build_object('message_id', p_message_id);
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_claim_decision IN ('terminal_completed', 'terminal_failed', 'terminal_rejected') THEN
        stage := 'claim';
        decision := v_claim_decision::TEXT;
        detail := jsonb_build_object('message_id', p_message_id);
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_claim_decision = 'claimed' AND v_item.status = 'processing' THEN
        stage := 'claim';
        decision := 'already_processing';
        detail := jsonb_build_object('message_id', p_message_id);
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT sl.decision, sl.holder
    INTO v_lock_decision, v_lock_holder
    FROM agent_runtime.acquire_session_lock(
        p_worker_id,
        p_user_id,
        p_session_id,
        p_message_id,
        p_session_lock_ttl_seconds
    ) AS sl;

    IF v_lock_decision = 'locked_by_other' THEN
        PERFORM agent_runtime.revert_work_assignment(p_worker_id, p_message_id);
        stage := 'session_lock';
        decision := 'locked_by_other';
        detail := jsonb_build_object('holder', v_lock_holder);
        RETURN NEXT;
        RETURN;
    END IF;

    v_acl_ok := agent_runtime.check_acl(p_protocol, p_user_id);
    IF NOT v_acl_ok THEN
        PERFORM agent_runtime.complete_work_item(p_worker_id, p_message_id, 'rejected', 'acl_denied');
        PERFORM agent_runtime.release_session_lock(p_worker_id, p_user_id, p_session_id);
        stage := 'acl';
        decision := 'rejected';
        detail := jsonb_build_object('reason', 'acl_denied');
        RETURN NEXT;
        RETURN;
    END IF;

    IF p_protocol = 'chat' THEN
        v_payment_ok := agent_runtime.check_payment_gate(p_user_id, p_session_id);
        IF NOT v_payment_ok THEN
            PERFORM agent_runtime.complete_work_item(p_worker_id, p_message_id, 'rejected', 'payment_required');
            PERFORM agent_runtime.release_session_lock(p_worker_id, p_user_id, p_session_id);
            stage := 'payment_gate';
            decision := 'rejected';
            detail := jsonb_build_object('reason', 'payment_required');
            RETURN NEXT;
            RETURN;
        END IF;
    END IF;

    SELECT r.allowed, r.limit_type, r.cooldown_seconds
    INTO v_rate_allowed, v_rate_type, v_rate_cooldown
    FROM agent_runtime.check_and_record_rate_limit(
        p_user_id,
        p_session_id,
        p_protocol
    ) AS r;

    IF NOT v_rate_allowed THEN
        PERFORM agent_runtime.complete_work_item(
            p_worker_id,
            p_message_id,
            'rejected',
            'rate_limit_' || v_rate_type
        );
        PERFORM agent_runtime.release_session_lock(p_worker_id, p_user_id, p_session_id);
        stage := 'rate_limit';
        decision := 'rejected';
        detail := jsonb_build_object(
            'limit_type', v_rate_type,
            'cooldown_seconds', v_rate_cooldown
        );
        RETURN NEXT;
        RETURN;
    END IF;

    v_item := agent_runtime.start_processing_work(
        p_worker_id,
        p_message_id,
        p_processing_ttl_seconds
    );

    IF v_item.message_id IS NULL THEN
        stage := 'claim';
        decision := 'already_processing';
        detail := jsonb_build_object('message_id', p_message_id);
        RETURN NEXT;
        RETURN;
    END IF;

    stage := 'ready';
    decision := 'processing';
    detail := jsonb_build_object(
        'message_id', p_message_id,
        'user_id', p_user_id,
        'session_id', p_session_id,
        'protocol', p_protocol,
        'payload', v_item.payload_json
    );
    RETURN NEXT;
END;
$$;

-- ---------------------------------------------------------------------------
-- finish_processing
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION agent_runtime.finish_processing(
    p_worker_id    TEXT,
    p_message_id   TEXT,
    p_user_id      TEXT,
    p_session_id   TEXT,
    p_success      BOOLEAN DEFAULT TRUE,
    p_error_reason TEXT DEFAULT NULL
)
RETURNS agent_runtime.work_items
LANGUAGE plpgsql
AS $$
DECLARE
    v_status agent_runtime.work_item_status;
    v_item   agent_runtime.work_items;
BEGIN
    v_status := CASE WHEN p_success THEN 'completed' ELSE 'failed' END;

    v_item := agent_runtime.complete_work_item(
        p_worker_id,
        p_message_id,
        v_status,
        p_error_reason
    );

    PERFORM agent_runtime.release_session_lock(p_worker_id, p_user_id, p_session_id);

    RETURN v_item;
END;
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE agent_runtime.work_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.session_locks ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.side_effect_outbox ENABLE ROW LEVEL SECURITY;

ALTER TABLE agent_runtime.work_items FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.session_locks FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.workers FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.side_effect_outbox FORCE ROW LEVEL SECURITY;

CREATE POLICY work_items_deny_direct_access
    ON agent_runtime.work_items FOR ALL TO agent_app
    USING (FALSE) WITH CHECK (FALSE);

CREATE POLICY session_locks_deny_direct_access
    ON agent_runtime.session_locks FOR ALL TO agent_app
    USING (FALSE) WITH CHECK (FALSE);

CREATE POLICY workers_deny_direct_access
    ON agent_runtime.workers FOR ALL TO agent_app
    USING (FALSE) WITH CHECK (FALSE);

CREATE POLICY side_effect_outbox_deny_direct_access
    ON agent_runtime.side_effect_outbox FOR ALL TO agent_app
    USING (FALSE) WITH CHECK (FALSE);

ALTER TABLE agent_runtime.conversation_history ENABLE ROW LEVEL SECURITY;
-- State tables below use permissive RLS (USING TRUE). The application MUST scope
-- every read/write by user_id and session_id; never expose cross-tenant APIs.
ALTER TABLE agent_runtime.persistent_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.session_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runtime.active_payment_requests ENABLE ROW LEVEL SECURITY;

ALTER TABLE agent_runtime.registered_with_agentverse ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversation_history_app_all
    ON agent_runtime.conversation_history FOR ALL TO agent_app
    USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY persistent_store_app_all
    ON agent_runtime.persistent_store FOR ALL TO agent_app
    USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY session_store_app_all
    ON agent_runtime.session_store FOR ALL TO agent_app
    USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY active_payment_requests_app_all
    ON agent_runtime.active_payment_requests FOR ALL TO agent_app
    USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY registered_with_agentverse_app_all
    ON agent_runtime.registered_with_agentverse FOR ALL TO agent_app
    USING (TRUE) WITH CHECK (TRUE);

-- ---------------------------------------------------------------------------
-- Function hardening + scoped grants
-- ---------------------------------------------------------------------------

ALTER FUNCTION agent_runtime.worker_active_count(TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.heartbeat_worker(TEXT, INTEGER, BOOLEAN, JSONB) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.reclaim_stale_work(INTEGER, INTEGER, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.enqueue_work_item(TEXT, TEXT, TEXT, TEXT, JSONB, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.claim_work_item(TEXT, TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.claim_next_pending_work(TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.revert_work_assignment(TEXT, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.acquire_session_lock(TEXT, TEXT, TEXT, TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.refresh_session_lock(TEXT, TEXT, TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.refresh_work_item_lease(TEXT, TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.release_session_lock(TEXT, TEXT, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.start_processing_work(TEXT, TEXT, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.complete_work_item(TEXT, TEXT, agent_runtime.work_item_status, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.has_side_effect(TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.record_side_effect(TEXT, TEXT, TEXT, JSONB) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.check_acl(TEXT, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.check_payment_gate(TEXT, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.check_and_record_rate_limit(TEXT, TEXT, TEXT) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.sync_protocol_acl(TEXT, TEXT, TEXT[]) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.sync_protocol_rate_limits(TEXT, INTEGER, INTEGER, INTEGER, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.purge_terminal_work_items(INTEGER, INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.purge_side_effect_outbox(INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.purge_idle_rate_counters(INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.purge_stale_workers(INTEGER) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.process_inbound_message(
    TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, INTEGER, INTEGER, INTEGER
) SECURITY DEFINER;
ALTER FUNCTION agent_runtime.finish_processing(TEXT, TEXT, TEXT, TEXT, BOOLEAN, TEXT) SECURITY DEFINER;

DO $$
DECLARE
    fn RECORD;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure AS signature
        FROM pg_proc AS p
        INNER JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'agent_runtime'
          AND p.prokind = 'f'
    LOOP
        EXECUTE format(
            'ALTER FUNCTION %s SET search_path = agent_runtime, pg_catalog',
            fn.signature
        );
    END LOOP;
END
$$;

REVOKE ALL ON SCHEMA agent_runtime FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA agent_runtime FROM PUBLIC;

GRANT USAGE ON SCHEMA agent_runtime TO agent_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    agent_runtime.conversation_history,
    agent_runtime.persistent_store,
    agent_runtime.session_store,
    agent_runtime.active_payment_requests,
    agent_runtime.registered_with_agentverse
TO agent_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA agent_runtime TO agent_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA agent_runtime TO agent_app;

-- ---------------------------------------------------------------------------
-- Pod login role (created by Postgres image from POSTGRES_USER / POSTGRES_PASSWORD)
-- ---------------------------------------------------------------------------

GRANT agent_app TO agent_pod;

COMMIT;
