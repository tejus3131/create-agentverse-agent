# Copyright (c) 2026 Tejus Gupta
"""Internal payment types (not exposed to agent developers)."""

from __future__ import annotations

from decimal import Decimal
from logging import Logger
from typing import Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, field_validator

type Amount = Decimal
type USDC = Amount
type FET = Amount
type Currency = str
type PaymentDescription = str
type Service = str
type ProductName = str
type AgentName = str
type IdempotencyKey = str
type TransactionID = str
type UserID = str
type SessionID = str
type MessageID = str
type AgentAddress = str
type AgentNetwork = Literal["testnet", "mainnet"]
type TimeoutSeconds = int


class VerificationResult(TypedDict):
    """Result of a payment verification attempt."""

    verified: bool
    error: str | None


class PaymentData(TypedDict):
    """Internal payment request data for provider orchestration."""

    amount: Amount
    currency: Currency
    description: PaymentDescription
    service: Service
    product_name: ProductName
    agent_name: AgentName
    idempotency_key: IdempotencyKey


class ActivePayment(TypedDict):
    """Pending payment tracked while user completes checkout."""

    usdc: USDC | None
    fet: FET | None
    message_id: MessageID
    idempotency_key: IdempotencyKey
    amount: NotRequired[Amount]
    currency: NotRequired[Currency]
    payment_method: NotRequired[str]


class PaymentContext(BaseModel):
    """Logging and correlation for payment provider calls."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    network: AgentNetwork
    logger: Logger
    user_id: UserID
    session_id: SessionID
    message_id: MessageID
    agent_address: AgentAddress
    wallet_address: AgentAddress
    fet_lcd_url: str

    @field_validator("agent_address", "wallet_address", mode="before")
    @classmethod
    def _coerce_address(cls, value: object) -> str:
        return str(value)

    @property
    def is_production(self) -> bool:
        """Skyfire/Stripe environment selection."""
        return self.network == "mainnet"


class TransactionEvent(TypedDict):
    """Cosmos transaction event."""

    type: str
    attributes: list[dict[str, str]]


class TransactionLog(TypedDict):
    """Cosmos transaction log entry."""

    msg_index: int
    log: str
    events: list[TransactionEvent]


class TransactionBody(TypedDict):
    """Cosmos transaction body."""

    messages: list[dict[str, Any]]
    memo: str
    timeout_height: str
    extension_options: list[Any]
    non_critical_extension_options: list[Any]


class Transaction(TypedDict):
    """Cosmos transaction envelope."""

    body: TransactionBody
    auth_info: dict[str, Any]
    signatures: list[str]


class TransactionResponse(TypedDict):
    """Cosmos transaction execution response."""

    height: str
    txhash: str
    codespace: str
    code: int
    data: str
    raw_log: str
    logs: list[TransactionLog]
    info: str
    gas_wanted: str
    gas_used: str
    tx: dict[str, Any]
    timestamp: str
    events: list[TransactionEvent]


class TransactionData(TypedDict):
    """LCD transaction query response."""

    tx: Transaction
    tx_response: TransactionResponse


def active_payment_to_storage(active: ActivePayment) -> dict[str, Any]:
    """Serialize active payment for Postgres JSONB.

    Returns:
        JSON-serializable active payment mapping.
    """
    payload: dict[str, Any] = {
        "usdc": str(active["usdc"]) if active["usdc"] is not None else None,
        "fet": str(active["fet"]) if active["fet"] is not None else None,
        "message_id": active["message_id"],
        "idempotency_key": active["idempotency_key"],
    }
    if "amount" in active:
        payload["amount"] = str(active["amount"])
    if "currency" in active:
        payload["currency"] = active["currency"]
    if "payment_method" in active:
        payload["payment_method"] = active["payment_method"]
    return payload


def active_payment_from_storage(data: dict[str, Any]) -> ActivePayment:
    """Deserialize active payment from Postgres JSONB.

    Returns:
        Active payment state for verification and follow-up handling.
    """
    usdc_raw = data.get("usdc")
    fet_raw = data.get("fet")
    active = ActivePayment(
        usdc=Decimal(str(usdc_raw)) if usdc_raw is not None else None,
        fet=Decimal(str(fet_raw)) if fet_raw is not None else None,
        message_id=str(data["message_id"]),
        idempotency_key=str(data["idempotency_key"]),
    )
    amount_raw = data.get("amount")
    if amount_raw is not None:
        active["amount"] = Decimal(str(amount_raw))
    currency_raw = data.get("currency")
    if currency_raw is not None:
        active["currency"] = str(currency_raw)
    payment_method_raw = data.get("payment_method")
    if payment_method_raw is not None:
        active["payment_method"] = str(payment_method_raw)
    return active
