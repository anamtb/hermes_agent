"""Adapter that delegates to the established Google Merchant MCP functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hermes_commerce.domain.product import CommerceProduct

from .base import BaseCommerceChannel
from .models import ChannelCapabilities


Tool = Callable[..., dict[str, Any]]


@dataclass
class GoogleMerchantChannel(BaseCommerceChannel):
    discover_tool: Tool
    preflight_tool: Tool
    publish_tool: Tool
    get_tool: Tool
    issues_tool: Tool

    name = "google_merchant"
    capabilities = ChannelCapabilities(
        supports_catalog_publish=True,
        supports_price_update=False,
        supports_stock_update=False,
        supports_orders=False,
        supports_shipping_policy=True,
    )

    def discover(self) -> dict[str, Any]:
        return self.discover_tool()

    @staticmethod
    def _product_arguments(product: CommerceProduct) -> dict[str, Any]:
        return {
            "offer_id": str(product.sku),
            "title": product.title,
            "description": product.description,
            "link": product.public_product_url,
            "image_link": product.image_url,
            "price_eur": str(product.gross_price.amount),
            "currency_code": product.gross_price.currency,
            "availability": product.inventory.availability.value,
            "condition": product.condition.value,
            "brand": product.brand,
            "mpn": product.mpn,
            "gtin": str(product.gtin) if product.gtin else None,
        }

    def preflight_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]:
        return self.preflight_tool(**self._product_arguments(product), **kwargs)

    def publish_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]:
        return self.publish_tool(**self._product_arguments(product), **kwargs)

    def get_product(self, external_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.get_tool(offer_id=external_id, **kwargs)

    def get_product_status(self, external_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.get_product(external_id, **kwargs)

    def get_product_issues(self, external_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.issues_tool(offer_id=external_id, **kwargs)
