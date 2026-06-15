# Copyright (c) 2026 Tejus Gupta
"""Developer-facing types for uAgents agent handlers.

These models describe what **your** handler receives and returns. Framework code
maps them to uAgents protocol messages and Postgres coordination (see ``new.db``).

Card support follows Agentverse interactive cards (ACP metadata path):
https://docs.agentverse.ai/documentation/advanced-usages/agent-driven-interactive-cards

Card support re-exports card models from ``uagents_core.contrib.protocols.chat.cards``
(``CarouselCardPayload``, ``FormCardPayload``, element-tree nodes, etc.).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)
from uagents_core.contrib.protocols.chat.cards import (
    BadgeNode,
    ButtonAction,
    ButtonNode,
    CarouselBadge,
    CarouselCardPayload,
    CarouselItem,
    ChoiceGridChoice,
    ChoiceGridNode,
    CtaAction,
    CustomCardPayload,
    DetailCardPayload,
    DetailSubOptionChoice,
    DetailSubOptions,
    DetailSummaryRow,
    DividerNode,
    ElementTreeNode,
    FormCardPayload,
    FormField,
    FormFieldOption,
    GroupNode,
    HeadingNode,
    ImageNode,
    InputNode,
    InputOption,
    ListItem,
    ListNode,
    ReviewCardPayload,
    ReviewSummaryRow,
    SectionNode,
    TextNode,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import timedelta


CardKind = Literal["carousel", "detail", "form", "review", "custom"]
SelectionValue = str | int | float | bool


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class Resource(BaseModel):
    """A URL attachment (image, file, link) sent with a message."""

    uri: str = Field(..., description="HTTP or HTTPS URL.")
    mime_type: str = Field(
        default="application/octet-stream",
        description="MIME type for the resource.",
    )

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        try:
            return str(HttpUrl(value))
        except ValidationError as exc:
            msg = f"Invalid resource URI: {value}"
            raise ValueError(msg) from exc


# ---------------------------------------------------------------------------
# Inbound requests (handler input)
# ---------------------------------------------------------------------------


class CardSelection(BaseModel):
    """User choice from an interactive card (CTA click or form submit).

    Matches ``CardResponse.selection`` from uAgents card helpers. Clients may also
    send the same data as JSON inside ``ChatInput.text`` (direct @mention) or as
    natural language prose (planner path) — use :func:`parse_card_selection_text`
    when ``selection`` is not already structured.
    """

    values: dict[str, SelectionValue] = Field(
        ...,
        description="Merged CTA selection + form field values.",
    )
    card_id: UUID | None = Field(
        default=None,
        description="Echo of the card_id from the outbound card, if provided.",
    )
    cancelled: bool = Field(
        default=False,
        description="True when the user dismissed the card without choosing.",
    )
    text: str | None = Field(
        default=None,
        description="Optional companion text from the client.",
    )


class ChatInput(BaseModel):
    """Inbound chat from the user (text, attachments, or card selection).

    Exactly one primary shape is usually set:

    - Plain chat: ``text`` (+ optional ``resources``)
    - Card reply: ``card_selection`` (preferred) or JSON in ``text``
    """

    text: str | None = Field(
        default=None,
        description="Plain message text, JSON selection string, or planner prose.",
    )
    resources: list[Resource] | None = Field(
        default=None,
        description="Attachments from ``ResourceContent`` blocks.",
    )
    card_selection: CardSelection | None = Field(
        default=None,
        description="Structured card interaction when client sends metadata path.",
    )

    @property
    def primary_text(self) -> str:
        """Best-effort single string for logging or simple echo handlers."""
        if self.text:
            return self.text
        if self.card_selection is not None:
            return json.dumps(self.card_selection.values, sort_keys=True)
        return ""


class PaymentUpdate(BaseModel):
    """Result of a payment protocol flow (after verify / reject)."""

    approved: bool = Field(..., description="True when payment succeeded.")
    reason: str | None = Field(
        default=None,
        description="Human-readable rejection reason when ``approved`` is false.",
    )
    transaction_id: str | None = Field(
        default=None,
        description="Provider transaction id when ``approved`` is true.",
    )


type HandlerRequest = ChatInput | PaymentUpdate
"""What your ``on_message`` handler receives for one work item."""


def parse_card_selection_text(text: str) -> CardSelection | None:
    """Try to parse ``ChatInput.text`` as card selection JSON.

    Per Agentverse docs, direct @mention clients send CTA ``selection`` as JSON in
    ``TextContent``. Planner-mediated clients send prose instead — return ``None`` and
    handle ``text`` with your own logic.

    Returns:
        CardSelection when ``text`` is valid selection JSON, else ``None``.
    """
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    values: dict[str, SelectionValue] = {}
    for key, val in raw.items():
        if isinstance(val, (str, int, float, bool)):
            values[str(key)] = val
    if not values:
        return None
    return CardSelection(values=values)


# ---------------------------------------------------------------------------
# Outbound responses (handler output)
# ---------------------------------------------------------------------------


class OutboundCard(BaseModel):
    """Interactive card to render in Agentverse / ASI:One clients.

    Wire format: ``MetadataContent`` with ``card_protocol_version=1`` (built by
    framework using ``create_card_content`` when available).

    See: https://docs.agentverse.ai/documentation/advanced-usages/predefined-card-schemas
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    payload: (
        CarouselCardPayload
        | FormCardPayload
        | DetailCardPayload
        | ReviewCardPayload
        | CustomCardPayload
    ) = Field(
        ...,
        description=(
            "Typed ``CarouselCardPayload`` / ``FormCardPayload`` / … when uAgents "
            "cards are installed, or a dict matching the schema for ``kind``."
        ),
    )
    card_id: UUID | None = Field(
        default=None,
        description="Optional correlation id; echo on the user's card response.",
    )
    is_terminal: bool = Field(
        default=False,
        description="Informational card only — do not set on cards that need input.",
    )
    preferred_drawer_width_px: int | None = Field(
        default=None,
        ge=320,
        le=800,
        description="UI hint for drawer width.",
    )


class TextReply(BaseModel):
    """Normal chat reply: text, optional attachments, optional interactive card."""

    text: str = Field(..., description="Message shown in the chat bubble.")
    resources: list[Resource] | None = Field(
        default=None,
        description="Optional attachments.",
    )
    card: OutboundCard | None = Field(
        default=None,
        description="Optional interactive card in the same ``ChatMessage``.",
    )


class PaymentRequest(BaseModel):
    """Ask the user to pay before continuing."""

    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    service: str = Field(..., min_length=1)


type HandlerResponse = TextReply | PaymentRequest
"""What your ``on_message`` handler returns."""


# ---------------------------------------------------------------------------
# Handler callables (what the developer registers)
# ---------------------------------------------------------------------------


@runtime_checkable
class AsyncMessageHandler(Protocol):
    """Async ``on_message`` implementation."""

    async def __call__(
        self,
        *,
        user_id: str,
        session_id: str,
        message_id: str,
        request: HandlerRequest,
    ) -> HandlerResponse:
        """Handle a message from the user."""
        ...


@runtime_checkable
class SyncMessageHandler(Protocol):
    """Sync ``on_message`` implementation (framework runs in a thread pool)."""

    def __call__(
        self,
        *,
        user_id: str,
        session_id: str,
        message_id: str,
        request: HandlerRequest,
    ) -> HandlerResponse:
        """Handle a message from the user."""
        ...


type MessageHandler = AsyncMessageHandler | SyncMessageHandler


@runtime_checkable
class LifecycleHook(Protocol):
    """``on_startup`` / ``on_shutdown`` hook."""

    async def __call__(self) -> None:
        """Hook to be called on agent startup or shutdown."""
        ...


@runtime_checkable
class SyncLifecycleHook(Protocol):
    """Sync lifecycle hook."""

    def __call__(self) -> None:
        """Hook to be called on agent startup or shutdown."""
        ...


type StartupHook = LifecycleHook | SyncLifecycleHook
type ShutdownHook = LifecycleHook | SyncLifecycleHook


@dataclass(slots=True)
class ScheduledTask:
    """Run ``handler`` on a fixed interval (framework ``on_interval`` wiring).

    Not cron syntax — use ``interval`` for "every N seconds/minutes".
    """

    interval: timedelta
    handler: Callable[[], Awaitable[None]] | Callable[[], None]
    name: str | None = None

    @property
    def interval_seconds(self) -> float:
        """Interval as seconds for uAgents ``on_interval``."""
        return self.interval.total_seconds()


@dataclass(slots=True)
class AgentDefinition:
    """Everything the developer defines for one agent.

    Example::

        async def handle_message(**kwargs) -> HandlerResponse:
            ...

        agent = AgentDefinition(
            on_message=handle_message,
            on_startup=[warm_cache],
            scheduled=[
                ScheduledTask(timedelta(hours=1), purge_metrics, name="metrics"),
            ],
        )
    """

    on_message: MessageHandler
    on_startup: list[StartupHook] = field(default_factory=list)
    on_shutdown: list[ShutdownHook] = field(default_factory=list)
    scheduled: list[ScheduledTask] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Type guards
# ---------------------------------------------------------------------------


def is_chat_input(request: HandlerRequest) -> bool:
    """Return True when ``request`` is a :class:`ChatInput`."""
    return isinstance(request, ChatInput)


def is_payment_update(request: HandlerRequest) -> bool:
    """Return True when ``request`` is a :class:`PaymentUpdate`."""
    return isinstance(request, PaymentUpdate)


def is_text_reply(response: HandlerResponse) -> bool:
    """Return True when ``response`` is a :class:`TextReply`."""
    return isinstance(response, TextReply)


def is_payment_request(response: HandlerResponse) -> bool:
    """Return True when ``response`` is a :class:`PaymentRequest`."""
    return isinstance(response, PaymentRequest)


__all__ = [
    "AgentDefinition",
    "AsyncMessageHandler",
    "BadgeNode",
    "ButtonAction",
    "ButtonNode",
    "CardKind",
    "CardSelection",
    "CarouselBadge",
    "CarouselCardPayload",
    "CarouselItem",
    "ChatInput",
    "ChoiceGridChoice",
    "ChoiceGridNode",
    "CtaAction",
    "CustomCardPayload",
    "DetailCardPayload",
    "DetailSubOptionChoice",
    "DetailSubOptions",
    "DetailSummaryRow",
    "DividerNode",
    "ElementTreeNode",
    "FormCardPayload",
    "FormField",
    "FormFieldOption",
    "GroupNode",
    "HandlerRequest",
    "HandlerResponse",
    "HeadingNode",
    "ImageNode",
    "InputNode",
    "InputOption",
    "LifecycleHook",
    "ListItem",
    "ListNode",
    "MessageHandler",
    "OutboundCard",
    "PaymentRequest",
    "PaymentUpdate",
    "Resource",
    "ReviewCardPayload",
    "ReviewSummaryRow",
    "ScheduledTask",
    "SectionNode",
    "SelectionValue",
    "ShutdownHook",
    "StartupHook",
    "SyncLifecycleHook",
    "SyncMessageHandler",
    "TextNode",
    "TextReply",
    "is_chat_input",
    "is_payment_request",
    "is_payment_update",
    "is_text_reply",
    "parse_card_selection_text",
]
