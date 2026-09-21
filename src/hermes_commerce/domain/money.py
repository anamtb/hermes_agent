"""Exact monetary and tax values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def as_decimal(name: str, value: Decimal | int | float | str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} debe ser numérico") from exc
    if not result.is_finite():
        raise ValueError(f"{name} debe ser finito")
    return result


@dataclass(frozen=True)
class Money:
    amount: Decimal | int | float | str
    currency: str

    def __post_init__(self) -> None:
        amount = as_decimal("amount", self.amount)
        currency = self.currency.strip().upper()
        if amount < 0:
            raise ValueError("amount no puede ser negativo")
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency debe ser un código ISO 4217")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True)
class Tax:
    """Decimal tax rate; 0.21 represents 21 percent."""

    rate: Decimal | int | float | str
    name: str | None = None

    def __post_init__(self) -> None:
        rate = as_decimal("tax rate", self.rate)
        if rate < 0 or rate > 1:
            raise ValueError("tax rate debe estar entre 0 y 1")
        object.__setattr__(self, "rate", rate)
