"""Channel-neutral stock and availability."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .money import as_decimal


class Availability(str, Enum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PREORDER = "PREORDER"
    BACKORDER = "BACKORDER"


@dataclass(frozen=True)
class Inventory:
    stock: Decimal | int | float | str
    availability: Availability

    def __post_init__(self) -> None:
        stock = as_decimal("stock", self.stock)
        if stock < 0:
            raise ValueError("stock no puede ser negativo")
        if self.availability == Availability.OUT_OF_STOCK and stock > 0:
            raise ValueError("OUT_OF_STOCK no puede tener stock positivo")
        object.__setattr__(self, "stock", stock)
