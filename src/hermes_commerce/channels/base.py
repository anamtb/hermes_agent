"""Small channel contract; adapters implement only advertised capabilities."""

from __future__ import annotations

from abc import ABC
from typing import Any, Protocol, runtime_checkable

from hermes_commerce.domain.product import CommerceProduct

from .models import ChannelCapabilities


class ChannelNotConfiguredError(RuntimeError):
    pass


class UnsupportedChannelOperation(NotImplementedError):
    pass


@runtime_checkable
class CommerceChannel(Protocol):
    name: str
    capabilities: ChannelCapabilities

    def discover(self) -> dict[str, Any]: ...
    def preflight_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]: ...
    def publish_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]: ...
    def get_product(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...
    def get_product_status(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...
    def get_product_issues(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...
    def update_price(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...
    def update_stock(self, external_id: str, **kwargs: Any) -> dict[str, Any]: ...


class BaseCommerceChannel(ABC):
    name = "base"
    capabilities = ChannelCapabilities()

    def require_configured(self, configured: bool) -> None:
        if not configured:
            raise ChannelNotConfiguredError(f"El canal {self.name} no está configurado")

    def _unsupported(self, operation: str) -> dict[str, Any]:
        raise UnsupportedChannelOperation(
            f"{self.name} no ofrece la operación {operation}"
        )

    def discover(self) -> dict[str, Any]: return self._unsupported("discover")
    def preflight_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]: return self._unsupported("preflight_product")
    def publish_product(self, product: CommerceProduct, **kwargs: Any) -> dict[str, Any]: return self._unsupported("publish_product")
    def get_product(self, external_id: str, **kwargs: Any) -> dict[str, Any]: return self._unsupported("get_product")
    def get_product_status(self, external_id: str, **kwargs: Any) -> dict[str, Any]: return self._unsupported("get_product_status")
    def get_product_issues(self, external_id: str, **kwargs: Any) -> dict[str, Any]: return self._unsupported("get_product_issues")
    def update_price(self, external_id: str, **kwargs: Any) -> dict[str, Any]: return self._unsupported("update_price")
    def update_stock(self, external_id: str, **kwargs: Any) -> dict[str, Any]: return self._unsupported("update_stock")
