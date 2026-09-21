"""Internal product model, deliberately free of marketplace identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from .identifiers import GTIN, SKU
from .inventory import Inventory
from .money import Money, Tax


class ProductCondition(str, Enum):
    NEW = "NEW"
    REFURBISHED = "REFURBISHED"
    USED = "USED"


@dataclass(frozen=True)
class SupplierCost:
    cost: Money
    supplier_reference: str | None = None


def _public_https_url(name: str, value: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"{name} debe ser una URL HTTPS pública")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{name} no puede incluir credenciales")
    return normalized


@dataclass(frozen=True)
class CommerceProduct:
    sku: SKU
    mpn: str
    brand: str
    title: str
    description: str
    net_price: Money
    gross_price: Money
    tax: Tax
    inventory: Inventory
    condition: ProductCondition
    image_url: str
    public_product_url: str
    gtin: GTIN | None = None
    supplier_cost: SupplierCost | None = None

    def __post_init__(self) -> None:
        for name in ("mpn", "brand", "title", "description"):
            normalized = getattr(self, name).strip()
            if not normalized:
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, normalized)
        if self.net_price.currency != self.gross_price.currency:
            raise ValueError("net_price y gross_price deben usar la misma moneda")
        if self.gross_price.amount < self.net_price.amount:
            raise ValueError("gross_price no puede ser menor que net_price")
        object.__setattr__(self, "image_url", _public_https_url("image_url", self.image_url))
        object.__setattr__(
            self,
            "public_product_url",
            _public_https_url("public_product_url", self.public_product_url),
        )
