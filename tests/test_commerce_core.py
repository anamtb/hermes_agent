import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from hermes_commerce.channels.base import (  # noqa: E402
    BaseCommerceChannel,
    ChannelNotConfiguredError,
)
from hermes_commerce.channels.google_merchant import GoogleMerchantChannel  # noqa: E402
from hermes_commerce.channels.models import (  # noqa: E402
    ChannelCapabilities,
    ChannelPricingInputs,
)
from hermes_commerce.domain import (  # noqa: E402
    Availability,
    CommerceProduct,
    GTIN,
    Inventory,
    Money,
    ProductCondition,
    SKU,
    Tax,
)
from hermes_commerce.workflows.product_launch import (  # noqa: E402
    ApprovalRequired,
    require_channel_approval,
)


def product(*, gtin=None):
    return CommerceProduct(
        sku=SKU("SKU-123"),
        mpn="MPN-123",
        gtin=gtin,
        brand="Example",
        title="Producto de prueba",
        description="Descripción verificable",
        net_price=Money("100", "EUR"),
        gross_price=Money("121", "EUR"),
        tax=Tax("0.21"),
        inventory=Inventory(4, Availability.IN_STOCK),
        condition=ProductCondition.NEW,
        image_url="https://shop.example/image.jpg",
        public_product_url="https://shop.example/product",
    )


class CommerceProductTests(unittest.TestCase):
    def test_product_represents_common_fields_without_channel_ids(self):
        value = product(gtin=GTIN("8592978652883"))

        self.assertEqual(str(value.sku), "SKU-123")
        self.assertEqual(str(value.gtin), "8592978652883")
        self.assertFalse(hasattr(value, "asin"))
        self.assertFalse(hasattr(value, "google_product_id"))

    def test_gtin_is_optional(self):
        self.assertIsNone(product().gtin)

    def test_sku_is_stable_in_google_mapping(self):
        preflight = Mock(return_value={"ok": True})
        channel = GoogleMerchantChannel(
            discover_tool=Mock(),
            preflight_tool=preflight,
            publish_tool=Mock(),
            get_tool=Mock(),
            issues_tool=Mock(),
        )

        channel.preflight_product(
            product(),
            data_source_id="1",
            content_language="es",
            feed_label="ES",
            public_price=121,
            public_currency="EUR",
            public_availability="IN_STOCK",
        )

        self.assertEqual(preflight.call_args.kwargs["offer_id"], "SKU-123")


class ChannelContractTests(unittest.TestCase):
    def test_capabilities_are_explicit(self):
        capabilities = ChannelCapabilities(supports_catalog_publish=True)
        self.assertTrue(capabilities.as_dict()["supports_catalog_publish"])
        self.assertFalse(capabilities.as_dict()["supports_orders"])

    def test_unknown_channel_cost_is_not_zero(self):
        values = ChannelPricingInputs(base_cost=100, shipping_cost=4).normalized()
        self.assertEqual(values["channel_fixed_fee"], "UNKNOWN")

    def test_unconfigured_channel_fails_explicitly(self):
        with self.assertRaises(ChannelNotConfiguredError):
            BaseCommerceChannel().require_configured(False)

    def test_approval_gate_requires_preflight_and_exact_confirmation(self):
        with self.assertRaises(ApprovalRequired):
            require_channel_approval(
                channel="example",
                confirmation="PUBLICAR",
                expected_confirmation="PUBLICAR",
                preflight_ready=False,
            )
        with self.assertRaises(ApprovalRequired):
            require_channel_approval(
                channel="example",
                confirmation="",
                expected_confirmation="PUBLICAR",
                preflight_ready=True,
            )

        require_channel_approval(
            channel="example",
            confirmation="PUBLICAR",
            expected_confirmation="PUBLICAR",
            preflight_ready=True,
        )


if __name__ == "__main__":
    unittest.main()
