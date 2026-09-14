import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "mcp"
    / "google-merchant"
    / "product_validation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "merchant_product_validation",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar product_validation")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_submission(**overrides):
    values = {
        "account_id": "123456",
        "data_source_id": "7890",
        "offer_id": "SKU-1",
        "title": "Producto",
        "description": "Descripción verificable",
        "link": "https://shop.example/products/sku-1",
        "image_link": "https://shop.example/images/sku-1.jpg",
        "price": 121.0,
        "currency_code": "EUR",
        "availability": "in_stock",
        "condition": "new",
        "brand": "Example",
        "mpn": "MPN-1",
        "content_language": "es",
        "feed_label": "ES",
    }
    values.update(overrides)
    return MODULE.build_product_submission(**values)


class MerchantProductValidationTests(unittest.TestCase):
    def test_normalizes_availability_and_identifiers(self) -> None:
        result = valid_submission()

        self.assertEqual(
            result["payload"]["productAttributes"]["availability"],
            "IN_STOCK",
        )
        self.assertEqual(result["product_id"], "es~ES~SKU-1")
        self.assertEqual(
            result["payload"]["productAttributes"]["price"],
            {"amountMicros": "121000000", "currencyCode": "EUR"},
        )

    def test_gtin_is_optional(self) -> None:
        result = valid_submission(gtin=None)

        self.assertNotIn("gtins", result["payload"]["productAttributes"])

    def test_invalid_gtin_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            valid_submission(gtin="not-a-gtin")

        with self.assertRaises(ValueError):
            valid_submission(gtin="8592978652884")

    def test_valid_gtin_checksum_is_preserved(self) -> None:
        result = valid_submission(gtin="8592978652883")

        self.assertEqual(
            result["payload"]["productAttributes"]["gtins"],
            ["8592978652883"],
        )

    def test_invalid_availability_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            valid_submission(availability="available")

    def test_schema_org_availability_is_normalized(self) -> None:
        for value in ("in-stock", "IN_STOCK", "https://schema.org/InStock"):
            with self.subTest(value=value):
                self.assertEqual(
                    MODULE.normalize_public_availability(value),
                    "IN_STOCK",
                )

    def test_condition_is_normalized(self) -> None:
        for value in ("new", "NEW", "https://schema.org/NewCondition"):
            with self.subTest(value=value):
                result = valid_submission(condition=value)
                self.assertEqual(
                    result["payload"]["productAttributes"]["condition"],
                    "NEW",
                )

    def test_decimal_and_float_prices_build_the_same_payload(self) -> None:
        decimal_result = valid_submission(price=Decimal("18997.00"))
        float_result = valid_submission(price=18997.0)

        self.assertEqual(
            decimal_result["payload"]["productAttributes"]["price"],
            float_result["payload"]["productAttributes"]["price"],
        )

    def test_currency_and_urls_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            valid_submission(currency_code="EU")

        with self.assertRaises(ValueError):
            valid_submission(link="https://user:password@example.com/product")

        with self.assertRaises(ValueError):
            valid_submission(image_link="http://example.com/image.jpg")

    def test_publication_confirmation_is_mandatory(self) -> None:
        with self.assertRaises(RuntimeError):
            MODULE.require_confirmation("", "PUBLICAR_EN_GOOGLE_MERCHANT")

        MODULE.require_confirmation(
            "PUBLICAR_EN_GOOGLE_MERCHANT",
            "PUBLICAR_EN_GOOGLE_MERCHANT",
        )


if __name__ == "__main__":
    unittest.main()
