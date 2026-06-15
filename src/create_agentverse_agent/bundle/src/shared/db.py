# Copyright (c) 2026 Tejus Gupta
"""Async Postgres client for the ``agent_runtime`` schema.

Wraps coordination functions, policy bootstrap, state tables, and pool lifecycle
described in ``new/docs/flow.md``. Use :class:`AgentRuntime` as the main entry
point from uAgents handlers and lifecycle hooks.

Example::

    runtime = await AgentRuntime.from_settings(worker_id="pod-1")
    pool = get_pool()
    async with runtime:
        result = await runtime.process_inbound(...)
        ...

Or explicit lifecycle::

    runtime = await AgentRuntime.open(dsn=..., worker_id="pod-1")
    try:
        await runtime.startup()
        ...
    finally:
        await runtime.shutdown()
        await runtime.close()
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Self

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from shared.settings import get_settings, parse_window_seconds

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

    from psycopg import AsyncConnection, AsyncCursor

    from shared.settings import AccessControl, RateLimits, Settings

ProtocolName = Literal["chat", "payment"]
EffectType = Literal["payment_charge", "chat_reply"]

_SILENT_CLAIM_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "worker_at_capacity",
        "worker_draining",
        "session_busy",
        "assigned_to_other",
        "already_processing",
    }
)

_TERMINAL_ENQUEUE_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "completed",
        "failed",
        "rejected",
    }
)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class ProcessStage(StrEnum):
    """Stages returned by ``process_inbound_message``."""

    ENQUEUE = "enqueue"
    CLAIM = "claim"
    SESSION_LOCK = "session_lock"
    ACL = "acl"
    PAYMENT_GATE = "payment_gate"
    RATE_LIMIT = "rate_limit"
    READY = "ready"


class ClaimDecision(StrEnum):
    """Claim outcomes from coordination functions."""

    ENQUEUED = "enqueued"
    ALREADY_ENQUEUED = "already_enqueued"
    CLAIMED = "claimed"
    NOT_FOUND = "not_found"
    WORKER_AT_CAPACITY = "worker_at_capacity"
    WORKER_DRAINING = "worker_draining"
    WORKER_NOT_REGISTERED = "worker_not_registered"
    SESSION_BUSY = "session_busy"
    ASSIGNED_TO_OTHER = "assigned_to_other"
    ALREADY_PROCESSING = "already_processing"
    TERMINAL_COMPLETED = "terminal_completed"
    TERMINAL_FAILED = "terminal_failed"
    TERMINAL_REJECTED = "terminal_rejected"


@dataclass(frozen=True, slots=True)
class ProcessInboundResult:
    """Result of ``process_inbound_message``."""

    stage: ProcessStage
    decision: str
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Normalized inbound work passed to the orchestrator."""

    message_id: str
    user_id: str
    session_id: str
    protocol: ProtocolName
    payload_json: dict[str, Any]
    schema_digest: str | None = None


@dataclass(frozen=True, slots=True)
class WorkItem:
    """Subset of ``work_items`` row used by the pipeline."""

    message_id: str
    user_id: str
    session_id: str
    protocol: str
    status: str
    payload_json: dict[str, Any]
    schema_digest: str | None


@dataclass(frozen=True, slots=True)
class ClaimNextResult:
    """Result of ``claim_next_pending_work``."""

    decision: ClaimDecision
    work_item: WorkItem | None


@dataclass(frozen=True, slots=True)
class ReclaimResult:
    """Counts from ``reclaim_stale_work``."""

    reclaimed_assigned: int
    reclaimed_processing: int
    reclaimed_session_locks: int


@dataclass(frozen=True, slots=True)
class PurgeWorkItemsResult:
    """Counts from ``purge_terminal_work_items``."""

    chat_outbox_deleted: int
    chat_items_deleted: int
    payment_outbox_deleted: int
    payment_items_deleted: int


@dataclass(frozen=True, slots=True)
class PurgeRateCountersResult:
    """Counts from ``purge_idle_rate_counters``."""

    session_counters_deleted: int
    user_counters_deleted: int


@dataclass(frozen=True, slots=True)
class WorkerRecord:
    """Registered pod row from ``heartbeat_worker``."""

    worker_id: str
    max_concurrent: int
    is_draining: bool


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One ``conversation_history`` row."""

    id: int
    actor_type: str
    actor_id: str
    session_id: str
    role: str
    message_type: str
    content_json: dict[str, Any]
    timestamp: str


# ---------------------------------------------------------------------------
# Flow helpers
# ---------------------------------------------------------------------------


def is_silent_skip(result: ProcessInboundResult) -> bool:
    """Return whether the orchestrator outcome must not surface a user error."""
    if (
        result.stage is ProcessStage.ENQUEUE
        and result.decision in _TERMINAL_ENQUEUE_DECISIONS
    ):
        return True
    if (
        result.stage is ProcessStage.CLAIM
        and result.decision in _SILENT_CLAIM_DECISIONS
    ):
        return True
    return bool(
        result.stage is ProcessStage.SESSION_LOCK
        and result.decision == "locked_by_other"
    )


def is_capacity_deferred(result: ProcessInboundResult) -> bool:
    """Return whether work was enqueued but deferred due to worker capacity."""
    return (
        result.stage is ProcessStage.CLAIM and result.decision == "worker_at_capacity"
    )


def is_deferred_ack(result: ProcessInboundResult) -> bool:
    """Return whether work was enqueued and should be acked before async processing."""
    return result.stage is ProcessStage.CLAIM and result.decision in {
        "worker_at_capacity",
        "session_busy",
    }


def is_payment_followup(
    result: ProcessInboundResult,
    inbound: InboundMessage,
) -> bool:
    """Return whether a payment commit/reject should invoke the dev handler.

    Payment outcomes reuse the original chat ``message_id`` after that work
    item is already terminal; coordination returns ``enqueue`` + completed.
    """
    return (
        inbound.protocol == "payment"
        and result.stage is ProcessStage.ENQUEUE
        and result.decision in _TERMINAL_ENQUEUE_DECISIONS
    )


def is_policy_reject(result: ProcessInboundResult) -> bool:
    """Return whether SQL already rejected the work item at a policy gate."""
    return (
        result.stage
        in {ProcessStage.ACL, ProcessStage.PAYMENT_GATE, ProcessStage.RATE_LIMIT}
        and result.decision == "rejected"
    )


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------


class PostgresPool:
    """Thin wrapper around :class:`psycopg_pool.AsyncConnectionPool`."""

    def __init__(self, conninfo: str, *, min_size: int = 1, max_size: int = 10) -> None:
        """Initialize the pool.

        Args:
            conninfo: The connection string to use for the pool.
            min_size: The minimum number of connections to keep in the pool.
            max_size: The maximum number of connections to keep in the pool.
        """
        self._pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=min_size,
            max_size=max_size,
            open=False,
        )
        self._open = False

    async def open(self) -> None:
        """Open the pool."""
        if not self._open:
            await self._pool.open()
            self._open = True

    async def close(self) -> None:
        """Close the pool."""
        if self._open:
            await self._pool.close()
            self._open = False

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[Any]]:
        """Borrow a connection from the pool.

        Yields:
            An AsyncConnection.
        """
        async with self._pool.connection() as conn:
            yield conn

    @property
    def is_open(self) -> bool:
        """Return whether the pool is open."""
        return self._open


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------


def _require_row[T: tuple[object, ...]](row: T | None, *, what: str) -> T:
    if row is None:
        msg = f"Expected database row for {what}"
        raise RuntimeError(msg)
    return row


def _json_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, Mapping):
        return dict(value)
    msg = f"Cannot coerce value to dict: {type(value).__name__}"
    raise TypeError(msg)


def _map_work_item(row: dict[str, Any] | None) -> WorkItem | None:
    if row is None or row.get("message_id") is None:
        return None
    return WorkItem(
        message_id=row["message_id"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        protocol=row["protocol"],
        status=row["status"],
        payload_json=_json_dict(row.get("payload_json")),
        schema_digest=row.get("schema_digest"),
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


async def verify_schema(pool: PostgresPool) -> None:
    """Fail fast when Postgres is unreachable or ``agent_runtime`` is missing.

    Args:
        pool: Open Postgres connection pool.

    Raises:
        RuntimeError: When Postgres is down or coordination schema was not applied.
    """
    try:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM agent_runtime.workers LIMIT 0")
    except Exception as exc:
        exc_chain = exc
        while exc_chain is not None:
            name = type(exc_chain).__name__
            text = str(exc_chain).lower()
            if name in {"OperationalError", "ConnectionFailed", "PoolTimeout"} or (
                "connection refused" in text or "couldn't get a connection" in text
            ):
                msg = (
                    "Postgres is not reachable — start the database with "
                    "'docker compose up -d' and confirm POSTGRES_HOST/POSTGRES_PORT "
                    "in .env match the published port (default localhost:5432)"
                )
                raise RuntimeError(msg) from exc
            exc_chain = exc_chain.__cause__  # type: ignore[assignment]

        msg = (
            "agent_runtime schema not found — apply schema.sql before startup "
            "(docker compose up -d applies it on first boot)"
        )
        raise RuntimeError(msg) from exc


async def bootstrap_runtime(pool: PostgresPool, settings: Settings) -> None:
    """Sync YAML-derived policy into Postgres (call on every pod startup)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await _sync_protocol(
            cur,
            "chat",
            settings.protocols.chat.access_control,
            settings.protocols.chat.rate_limits,
        )
        await _sync_protocol(
            cur,
            "payment",
            settings.protocols.payment.access_control,
            settings.protocols.payment.rate_limits,
        )


async def _sync_protocol(
    cur: AsyncCursor[tuple[object, ...]],
    protocol: ProtocolName,
    acl: AccessControl,
    rates: RateLimits,
) -> None:
    """Sync protocol ACL and rate limits.

    Args:
        cur: The cursor to use for the protocol.
        protocol: The protocol to sync.
        acl: The ACL to sync.
        rates: The rate limits to sync.
    """
    await cur.execute(
        "SELECT agent_runtime.sync_protocol_acl(%s, %s, %s)",
        (protocol, acl.policy, list(acl.identifiers or ())),
    )
    await cur.execute(
        """
        SELECT agent_runtime.sync_protocol_rate_limits(%s, %s, %s, %s, %s)
        """,
        (
            protocol,
            rates.session.max_requests,
            parse_window_seconds(rates.session.window),
            rates.user.max_requests,
            parse_window_seconds(rates.user.window),
        ),
    )


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class RuntimeCoordinator:
    """SQL wrapper for multipod coordination functions."""

    def __init__(
        self,
        pool: PostgresPool,
        worker_id: str,
        settings: Settings,
    ) -> None:
        """Initialize the coordinator.

        Args:
            pool: The pool to use for the coordinator.
            worker_id: The worker ID to use for the coordinator.
            settings: The settings to use for the coordinator.
        """
        self._pool = pool
        self._worker_id = worker_id
        self._settings = settings

    @property
    def worker_id(self) -> str:
        """Registered pod identifier."""
        return self._worker_id

    async def heartbeat_worker(
        self,
        *,
        is_draining: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> WorkerRecord:
        """Register or refresh this pod in ``workers``.

        Args:
            is_draining: Whether the worker is draining.
            metadata: The metadata to use for the worker.

        Returns:
            A WorkerRecord.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT worker_id, max_concurrent, is_draining
                    FROM agent_runtime.heartbeat_worker(%s, %s, %s, %s)
                    """,
                (
                    self._worker_id,
                    self._settings.runtime.max_concurrent_sessions,
                    is_draining,
                    Jsonb(metadata or {}),
                ),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="heartbeat_worker")
        return WorkerRecord(
            worker_id=row[0],
            max_concurrent=row[1],
            is_draining=row[2],
        )

    async def reclaim_stale_work(self) -> ReclaimResult:
        """Reclaim assigned/processing work and stale session locks.

        Returns:
            A ReclaimResult.
        """
        stale = self._settings.runtime.coordinator.reclaim_worker_stale_seconds
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT reclaimed_assigned, reclaimed_processing,
                        reclaimed_session_locks
                    FROM agent_runtime.reclaim_stale_work(0, 0, %s)
                    """,
                (stale,),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="reclaim_stale_work")
        return ReclaimResult(row[0], row[1], row[2])

    async def process_inbound(self, msg: InboundMessage) -> ProcessInboundResult:
        """Run the full orchestrator for one inbound message.

        Args:
            msg: The inbound message to process.

        Returns:
            A ProcessInboundResult.
        """
        coordinator = self._settings.runtime.coordinator
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT stage, decision, detail
                    FROM agent_runtime.process_inbound_message(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                (
                    self._worker_id,
                    msg.message_id,
                    msg.user_id,
                    msg.session_id,
                    msg.protocol,
                    Jsonb(msg.payload_json),
                    msg.schema_digest,
                    coordinator.assignment_ttl_seconds,
                    self._settings.processing_ttl_seconds(),
                    coordinator.session_lock_ttl_seconds,
                ),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="process_inbound_message")
        return ProcessInboundResult(
            stage=ProcessStage(row[0]),
            decision=row[1],
            detail=_json_dict(row[2]),
        )

    async def finish_processing(
        self,
        *,
        message_id: str,
        user_id: str,
        session_id: str,
        success: bool = True,
        error_reason: str | None = None,
    ) -> str | None:
        """Mark work terminal and release the session lock.

        Args:
            message_id: The message ID to finish processing.
            user_id: The user ID to finish processing.
            session_id: The session ID to finish processing.
            success: Whether the processing was successful.
            error_reason: The error reason if the processing was not successful.

        Returns:
            The status of the work item.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT status
                    FROM agent_runtime.finish_processing(
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                (
                    self._worker_id,
                    message_id,
                    user_id,
                    session_id,
                    success,
                    error_reason,
                ),
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def claim_next_pending(self) -> ClaimNextResult:
        """Claim one session-aware pending item for drain.

        Returns:
            The status of the work item.
        """
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT
                    t.decision::text AS decision,
                    (t.work_item).message_id AS message_id,
                    (t.work_item).user_id AS user_id,
                    (t.work_item).session_id AS session_id,
                    (t.work_item).protocol AS protocol,
                    (t.work_item).status AS status,
                    (t.work_item).payload_json AS payload_json,
                    (t.work_item).schema_digest AS schema_digest
                FROM agent_runtime.claim_next_pending_work(%s, %s) AS t
                """,
                (
                    self._worker_id,
                    self._settings.runtime.coordinator.assignment_ttl_seconds,
                ),
            )
            row = await cur.fetchone()
        if row is None:
            return ClaimNextResult(ClaimDecision.NOT_FOUND, None)
        decision = ClaimDecision(row["decision"])
        work_item = _map_work_item(row) if decision is ClaimDecision.CLAIMED else None
        return ClaimNextResult(decision, work_item)

    async def refresh_session_lock(self, user_id: str, session_id: str) -> bool:
        """Extend session lock TTL during long handlers.

        Args:
            user_id: The user ID to refresh the session lock for.
            session_id: The session ID to refresh the session lock for.

        Returns:
            True if the session lock was refreshed, False otherwise.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT agent_runtime.refresh_session_lock(
                        %s, %s, %s, %s
                    )
                    """,
                (
                    self._worker_id,
                    user_id,
                    session_id,
                    self._settings.runtime.coordinator.session_lock_ttl_seconds,
                ),
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def refresh_work_item_lease(self, message_id: str) -> bool:
        """Extend processing lease during long handlers.

        Args:
            message_id: The message ID to refresh the work item lease for.

        Returns:
            True if the work item lease was refreshed, False otherwise.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT agent_runtime.refresh_work_item_lease(
                        %s, %s, %s
                    )
                    """,
                (
                    self._worker_id,
                    message_id,
                    self._settings.processing_ttl_seconds(),
                ),
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def refresh_leases(
        self,
        *,
        user_id: str,
        session_id: str,
        message_id: str,
    ) -> None:
        """Refresh session lock and work item lease together.

        Args:
            user_id: The user ID to refresh the session lock for.
            session_id: The session ID to refresh the session lock for.
            message_id: The message ID to refresh the work item lease for.
        """
        await self.refresh_session_lock(user_id, session_id)
        await self.refresh_work_item_lease(message_id)

    async def has_side_effect(self, idempotency_key: str) -> bool:
        """Check whether an external side effect was already recorded.

        Args:
            idempotency_key: The idempotency key to check.

        Returns:
            True if the side effect was already recorded, False otherwise.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_runtime.has_side_effect(%s)",
                (idempotency_key,),
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def record_side_effect(
        self,
        *,
        message_id: str,
        effect_type: EffectType,
        idempotency_key: str,
        payload_json: dict[str, Any] | None = None,
    ) -> bool:
        """Record an external side effect (returns False if key already exists).

        Args:
            message_id: The message ID to record the side effect for.
            effect_type: The type of side effect to record.
            idempotency_key: The idempotency key to record.
            payload_json: The payload JSON to record.

        Returns:
            True if the side effect was recorded, False otherwise.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT agent_runtime.record_side_effect(%s, %s, %s, %s)
                    """,
                (
                    message_id,
                    effect_type,
                    idempotency_key,
                    Jsonb(payload_json or {}),
                ),
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def worker_active_count(self) -> int:
        """Return active assigned/processing items for this worker.

        Returns:
            The number of active assigned/processing items for this worker.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_runtime.worker_active_count(%s)",
                (self._worker_id,),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def purge_terminal_work_items(
        self,
        *,
        chat_days: int = 7,
        payment_days: int = 365,
    ) -> PurgeWorkItemsResult:
        """Delete old terminal work items and related chat outbox rows.

        Args:
            chat_days: The number of days to purge chat work items.
            payment_days: The number of days to purge payment work items.

        Returns:
            A PurgeWorkItemsResult.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT chat_outbox_deleted, chat_items_deleted,
                        payment_outbox_deleted, payment_items_deleted
                    FROM agent_runtime.purge_terminal_work_items(%s, %s)
                    """,
                (chat_days, payment_days),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="purge_terminal_work_items")
        return PurgeWorkItemsResult(*row)

    async def purge_side_effect_outbox(self, *, days: int = 365) -> int:
        """Delete orphaned outbox rows older than ``days``.

        Args:
            days: The number of days to purge the side effect outbox.

        Returns:
            The number of rows deleted from the side effect outbox.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_runtime.purge_side_effect_outbox(%s)",
                (days,),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def purge_idle_rate_counters(
        self, *, days: int = 30
    ) -> PurgeRateCountersResult:
        """Delete stale rate counter rows.

        Args:
            days: The number of days to purge the idle rate counters.

        Returns:
            A PurgeRateCountersResult.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT session_counters_deleted, user_counters_deleted
                    FROM agent_runtime.purge_idle_rate_counters(%s)
                    """,
                (days,),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="purge_idle_rate_counters")
        return PurgeRateCountersResult(*row)

    async def purge_stale_workers(self, *, heartbeat_stale_seconds: int = 86400) -> int:
        """Remove drained workers with stale heartbeats and no active work.

        Args:
            heartbeat_stale_seconds: The number of seconds to purge the stale workers.

        Returns:
            The number of rows deleted from the workers table.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_runtime.purge_stale_workers(%s)",
                (heartbeat_stale_seconds,),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# State repository
# ---------------------------------------------------------------------------


class StateRepository:
    """CRUD for durable state tables granted to ``agent_app``.

    Tenant contract: every method scopes data by ``user_id`` and ``session_id``
    where applicable. Do not add APIs that list or mutate rows across users.
    """

    def __init__(self, pool: PostgresPool) -> None:
        """Initialize the StateRepository.

        Args:
            pool: The pool to use for the StateRepository.
        """
        self._pool = pool

    async def append_history(
        self,
        *,
        actor_id: str,
        session_id: str,
        role: str,
        message_type: str,
        content_json: dict[str, Any],
        actor_type: str = "user",
    ) -> int:
        """Append a row to ``conversation_history``.

        Args:
            actor_id: The ID of the actor.
            session_id: The ID of the session.
            role: The role of the actor.
            message_type: The type of message.
            content_json: The content of the message.
            actor_type: The type of actor.

        Returns:
            The ID of the new row.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.conversation_history (
                        actor_type, actor_id, session_id, role,
                        message_type, content_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                (
                    actor_type,
                    actor_id,
                    session_id,
                    role,
                    message_type,
                    Jsonb(content_json),
                ),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="append_history")
        return int(row[0])

    async def list_history(
        self,
        actor_id: str,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[HistoryEntry]:
        """List conversation history oldest-first.

        Args:
            actor_id: The ID of the actor.
            session_id: The ID of the session.
            limit: The maximum number of rows to return.

        Returns:
            A list of HistoryEntry objects.
        """
        async with (
            self._pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cur,
        ):
            await cur.execute(
                """
                SELECT id, actor_type, actor_id, session_id, role,
                        message_type, content_json, timestamp::text
                FROM agent_runtime.conversation_history
                WHERE actor_id = %s AND session_id = %s
                ORDER BY timestamp ASC
                LIMIT %s
                """,
                (actor_id, session_id, limit),
            )
            rows = await cur.fetchall()
        return [
            HistoryEntry(
                id=row["id"],
                actor_type=row["actor_type"],
                actor_id=row["actor_id"],
                session_id=row["session_id"],
                role=row["role"],
                message_type=row["message_type"],
                content_json=_json_dict(row["content_json"]),
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    async def get_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        """Read session-scoped JSON store.

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.

        Returns:
            The session-scoped JSON store.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT value
                    FROM agent_runtime.session_store
                    WHERE user_id = %s AND session_id = %s
                    """,
                (user_id, session_id),
            )
            row = await cur.fetchone()
        return _json_dict(row[0]) if row else None

    async def set_session(
        self,
        user_id: str,
        session_id: str,
        value: dict[str, Any],
    ) -> None:
        """Upsert session-scoped JSON store.

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.
            value: The value to upsert into the session store.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.session_store (user_id, session_id, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, session_id) DO UPDATE
                    SET value = EXCLUDED.value
                    """,
                (user_id, session_id, Jsonb(value)),
            )

    async def patch_session(
        self,
        user_id: str,
        session_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge ``patch`` into session store JSON.

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.
            patch: The patch to merge into the session store.

        Returns:
            The merged session store.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.session_store (user_id, session_id, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, session_id) DO UPDATE
                    SET value = agent_runtime.session_store.value || EXCLUDED.value
                    RETURNING value
                    """,
                (user_id, session_id, Jsonb(patch)),
            )
            row = await cur.fetchone()
        row = _require_row(row, what="patch_session")
        return _json_dict(row[0])

    async def get_persistent(self, user_id: str) -> dict[str, Any] | None:
        """Read user-scoped persistent JSON store.

        Args:
            user_id: The ID of the user.

        Returns:
            The user-scoped persistent JSON store.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT value
                    FROM agent_runtime.persistent_store
                    WHERE user_id = %s
                    """,
                (user_id,),
            )
            row = await cur.fetchone()
        return _json_dict(row[0]) if row else None

    async def set_persistent(self, user_id: str, value: dict[str, Any]) -> None:
        """Upsert user-scoped persistent JSON store.

        Args:
            user_id: The ID of the user.
            value: The value to upsert into the persistent store.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.persistent_store (user_id, value)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET value = EXCLUDED.value
                    """,
                (user_id, Jsonb(value)),
            )

    async def get_active_payment(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        """Read pending payment metadata (blocks chat via payment gate).

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.

        Returns:
            The pending payment metadata.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT value
                    FROM agent_runtime.active_payment_requests
                    WHERE user_id = %s AND session_id = %s
                    """,
                (user_id, session_id),
            )
            row = await cur.fetchone()
        return _json_dict(row[0]) if row else None

    async def set_active_payment(
        self,
        user_id: str,
        session_id: str,
        value: dict[str, Any],
    ) -> None:
        """Store pending payment metadata.

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.
            value: The value to store into the active payment requests.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.active_payment_requests
                        (user_id, session_id, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, session_id) DO UPDATE
                    SET value = EXCLUDED.value
                    """,
                (user_id, session_id, Jsonb(value)),
            )

    async def remove_active_payment(self, user_id: str, session_id: str) -> None:
        """Clear pending payment metadata.

        Args:
            user_id: The ID of the user.
            session_id: The ID of the session.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    DELETE FROM agent_runtime.active_payment_requests
                    WHERE user_id = %s AND session_id = %s
                    """,
                (user_id, session_id),
            )

    async def is_registered(self, agent_address: str) -> bool:
        """Return whether Agentverse registration was recorded.

        Args:
            agent_address: The address of the agent.

        Returns:
            True if the agent was registered, False otherwise.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT 1
                    FROM agent_runtime.registered_with_agentverse
                    WHERE user_id = %s
                    """,
                (agent_address,),
            )
            row = await cur.fetchone()
        return row is not None

    async def mark_registered(
        self,
        agent_address: str,
        metadata: dict[str, Any],
    ) -> None:
        """Record Agentverse registration for ``agent_address``.

        Args:
            agent_address: The address of the agent.
            metadata: The metadata to store for the agent.
        """
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    INSERT INTO agent_runtime.registered_with_agentverse
                        (user_id, value)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET value = EXCLUDED.value
                    """,
                (agent_address, Jsonb(metadata)),
            )


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


class AgentRuntime:
    """High-level client combining pool, coordinator, state, and bootstrap."""

    _instance: ClassVar[AgentRuntime | None] = None

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        """Create a new AgentRuntime instance.

        Args:
            *args: The arguments to pass to the superclass.
            **kwargs: The keyword arguments to pass to the superclass.

        Returns:
            The AgentRuntime instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        pool: PostgresPool,
        coordinator: RuntimeCoordinator,
        state: StateRepository,
        settings: Settings,
    ) -> None:
        """Initialize the AgentRuntime.

        Args:
            pool: The pool to use for the AgentRuntime.
            coordinator: The coordinator to use for the AgentRuntime.
            state: The state repository to use for the AgentRuntime.
            settings: The settings to use for the AgentRuntime.
        """
        if hasattr(self, "pool"):
            return
        self.pool = pool
        self.coordinator = coordinator
        self.state = state
        self.settings = settings
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed or not self.pool.is_open:
            msg = (
                "AgentRuntime is closed; open a new instance with "
                "AgentRuntime.from_settings()"
            )
            raise RuntimeError(msg)

    @classmethod
    async def open(
        cls,
        *,
        dsn: str | None = None,
        worker_id: str,
        settings: Settings | None = None,
        min_pool_size: int = 1,
        max_pool_size: int = 10,
    ) -> Self:
        """Open the shared pool and construct runtime clients.

        Args:
            dsn: Optional libpq connection string override.
            worker_id: The worker ID to use for the AgentRuntime.
            settings: Settings loaded from agent.yml and env secrets.
            min_pool_size: The minimum number of connections to keep in the pool.
            max_pool_size: The maximum number of connections to keep in the pool.

        Returns:
            The cached open AgentRuntime instance.
        """
        if (
            cls._instance is not None
            and not cls._instance._closed
            and cls._instance.pool.is_open
        ):
            return cls._instance

        cls._instance = None
        runtime_settings = settings or get_settings()
        conninfo = dsn or runtime_settings.postgres_conninfo(f"uagent-{worker_id}")

        pool = PostgresPool(conninfo, min_size=min_pool_size, max_size=max_pool_size)
        await pool.open()

        coordinator = RuntimeCoordinator(pool, worker_id, runtime_settings)
        state = StateRepository(pool)
        return cls(pool, coordinator, state, runtime_settings)

    async def __aenter__(self) -> Self:
        """Enter async context: run startup hooks.

        Returns:
            This runtime instance.
        """
        await self.startup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit async context: drain flag + close pool."""
        if not self._closed:
            await self.shutdown()
            await self.close()

    @classmethod
    async def from_settings(
        cls,
        *,
        worker_id: str,
        settings: Settings | None = None,
    ) -> Self:
        """Open runtime using settings from agent.yml and env secrets.

        Args:
            worker_id: The worker ID to use for the AgentRuntime.
            settings: Optional settings override. Defaults to :func:`get_settings`.

        Returns:
            An AgentRuntime instance.
        """
        return await cls.open(worker_id=worker_id, settings=settings)

    async def close(self) -> None:
        """Close the underlying pool. Safe to call more than once."""
        if self._closed:
            return
        await self.pool.close()
        self._closed = True
        type(self)._instance = None

    async def startup(self) -> WorkerRecord:
        """Pod startup: heartbeat, bootstrap policy, reclaim stale work.

        Returns:
            A WorkerRecord.
        """
        self._ensure_open()
        worker = await self.coordinator.heartbeat_worker(is_draining=False)
        await bootstrap_runtime(self.pool, self.settings)
        await self.coordinator.reclaim_stale_work()
        return worker

    async def shutdown(self, *, is_draining: bool = True) -> WorkerRecord:
        """Pod shutdown: mark draining (do not delete ``workers`` rows).

        Args:
            is_draining: Whether the worker is draining.

        Returns:
            A WorkerRecord.
        """
        self._ensure_open()
        return await self.coordinator.heartbeat_worker(is_draining=is_draining)

    async def tick(self) -> ReclaimResult:
        """Background interval: heartbeat + reclaim stale coordination state.

        Returns:
            A ReclaimResult.
        """
        self._ensure_open()
        await self.coordinator.heartbeat_worker(is_draining=False)
        return await self.coordinator.reclaim_stale_work()

    async def process_inbound(self, msg: InboundMessage) -> ProcessInboundResult:
        """Delegate to :meth:`RuntimeCoordinator.process_inbound`.

        Args:
            msg: The inbound message to process.

        Returns:
            A ProcessInboundResult.
        """
        self._ensure_open()
        return await self.coordinator.process_inbound(msg)

    async def finish_processing(
        self,
        *,
        message_id: str,
        user_id: str,
        session_id: str,
        success: bool = True,
        error_reason: str | None = None,
    ) -> str | None:
        """Delegate to :meth:`RuntimeCoordinator.finish_processing`.

        Args:
            message_id: The message ID to finish processing.
            user_id: The user ID to finish processing.
            session_id: The session ID to finish processing.
            success: Whether the processing was successful.
            error_reason: The error reason if the processing was not successful.

        Returns:
            The status of the work item.
        """
        self._ensure_open()
        return await self.coordinator.finish_processing(
            message_id=message_id,
            user_id=user_id,
            session_id=session_id,
            success=success,
            error_reason=error_reason,
        )

    async def drain_once(self) -> ClaimNextResult:
        """Claim at most one pending item for follow-up processing.

        Returns:
            A ClaimNextResult.
        """
        self._ensure_open()
        return await self.coordinator.claim_next_pending()

    @staticmethod
    def inbound_from_work_item(item: WorkItem) -> InboundMessage:
        """Rebuild :class:`InboundMessage` from a claimed drain item.

        Args:
            item: The work item to rebuild the inbound message from.

        Returns:
            An InboundMessage.

        Raises:
            ValueError: If the protocol is not supported.
        """
        protocol = item.protocol
        if protocol not in {"chat", "payment"}:
            msg = f"Unsupported protocol: {protocol}"
            raise ValueError(msg)
        return InboundMessage(
            message_id=item.message_id,
            user_id=item.user_id,
            session_id=item.session_id,
            protocol=protocol,
            payload_json=item.payload_json,
            schema_digest=item.schema_digest,
        )


def get_agent_runtime() -> AgentRuntime:
    """Return the open AgentRuntime singleton.

    Returns:
        The cached AgentRuntime instance.

    Raises:
        RuntimeError: If the runtime has not been opened or is closed.
    """
    instance = AgentRuntime._instance
    if instance is None or instance._closed or not instance.pool.is_open:
        msg = "AgentRuntime is not open; call AgentRuntime.from_settings() first"
        raise RuntimeError(msg)
    return instance


def get_pool() -> PostgresPool:
    """Return the Postgres pool from the open AgentRuntime singleton.

    Returns:
        The shared connection pool.
    """
    return get_agent_runtime().pool
