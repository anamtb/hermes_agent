"""Common channel metadata kept separate from CommerceProduct."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from hermes_commerce.domain.money import as_decimal


UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ChannelCapabilities:
    supports_catalog_publish: bool = False
    supports_price_update: bool = False
    supports_stock_update: bool = False
    supports_orders: bool = False
    supports_shipping_policy: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "supports_catalog_publish": self.supports_catalog_publish,
            "supports_price_update": self.supports_price_update,
            "supports_stock_update": self.supports_stock_update,
            "supports_orders": self.supports_orders,
            "supports_shipping_policy": self.supports_shipping_policy,
        }


@dataclass(frozen=True)
class ChannelIdentifier:
    channel: str
    external_id: str
    seller_sku: str


@dataclass(frozen=True)
class ChannelPricingInputs:
    """Per-channel costs. None means UNKNOWN, never an inferred zero."""

    base_cost: Decimal | int | float | str
    shipping_cost: Decimal | int | float | str | None = None
    channel_fixed_fee: Decimal | int | float | str | None = None
    channel_percent_fee: Decimal | int | float | str | None = None
    other_channel_costs: Decimal | int | float | str | None = None

    def normalized(self) -> dict[str, Decimal | str]:
        result: dict[str, Decimal | str] = {
            "base_cost": as_decimal("base_cost", self.base_cost)
        }
        for name in (
            "shipping_cost",
            "channel_fixed_fee",
            "channel_percent_fee",
            "other_channel_costs",
        ):
            value: Any = getattr(self, name)
            result[name] = UNKNOWN if value is None else as_decimal(name, value)
        return result

    @property
    def costs_complete(self) -> bool:
        return all(
            getattr(self, name) is not None
            for name in (
                "shipping_cost",
                "channel_fixed_fee",
                "channel_percent_fee",
                "other_channel_costs",
            )
        )
