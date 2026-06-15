# Copyright (c) 2026 Tejus Gupta
"""Protocol stubs (full wiring in later phases)."""

from runtime.protocols.chat import extract_message_context, setup_chat_protocol
from runtime.protocols.payment import setup_payment_protocol

__all__ = [
    "extract_message_context",
    "setup_chat_protocol",
    "setup_payment_protocol",
]
