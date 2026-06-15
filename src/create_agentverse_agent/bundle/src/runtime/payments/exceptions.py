# Copyright (c) 2026 Tejus Gupta
"""Internal payment exceptions (runtime only)."""


class PaymentConversionError(Exception):
    """Raised when payment amount conversion fails."""

    def __init__(self, message: str) -> None:
        """Store a conversion failure message."""
        super().__init__(message)
        self.message = message
