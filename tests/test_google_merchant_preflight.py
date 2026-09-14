import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "mcp" / "google-merchant" / "google_merchant_mcp.py"
)
MODULE_DIR = str(MODULE_PATH.parent)

if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

SPEC = importlib.util.spec_from_file_location(
    "google_merchant_preflight_regression",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar google_merchant_mcp")

MERCHANT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERCHANT)


def real_product(**overrides):
    values = {
        "data_source_id": "10723482068",
        "offer_id": "900-2G153-0000-000",
        "title": "NVIDIA RTX PRO 6000 Blackwell Server Edition 96GB",
        "description": (
            "NVIDIA RTX PRO 6000 Blackwell Server Edition con 96 GB de "
            "memoria GDDR7 ECC, basada en arquitectura NVIDIA Blackwell y "
            "diseñada para servidores y centros de datos. Incorpora 24.064 "
            "núcleos CUDA, interfaz PCIe 5.0 x16, refrigeración pasiva y un "
            "consumo máximo de hasta 600 W."
        ),
        "link": (
            "https://pianato.odoo.com/shop/900-2g153-0000-000-nvidia-rtx-"
            "pro-6000-blackwell-server-edition-96gb-7"
        ),
        "image_link": (
            "https://pianato.odoo.com/web/image/product.template/7/image_1920"
        ),
        "price_eur": 18997,
        "currency_code": "EUR",
        "availability": "in-stock",
        "brand": "NVIDIA",
        "mpn": "900-2G153-0000-000",
        "gtin": "8592978652883",
        "condition": "new",
        "content_language": "es",
        "feed_label": "ES",
        "public_price": 18997,
        "public_currency": "EUR",
        "public_availability": "in-stock",
    }
    values.update(overrides)
    return values


def successful_url_check(url: str, *, require_image: bool):
    return {
        "url": url,
        "final_url": url,
        "status_code": 200,
        "content_type": "image/jpeg" if require_image else "text/html",
        "public": True,
        "error": None,
    }


class GoogleMerchantPreflightRegressionTests(unittest.TestCase):
    @patch.object(MERCHANT, "_merchant_post")
    @patch.object(MERCHANT, "_merchant_get")
    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_exact_production_payload_is_valid_without_merchant_api_calls(
        self,
        configured_account,
        check_public_url,
        merchant_get,
        merchant_post,
    ) -> None:
        result = MERCHANT.google_merchant_preflight_product(**real_product())

        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], [])
        self.assertFalse(result["published"])
        self.assertEqual(result["normalized"], result["submission"])
        self.assertEqual(
            result["normalized"]["data_source"],
            "accounts/123456/dataSources/10723482068",
        )
        attributes = result["normalized"]["payload"]["productAttributes"]
        self.assertEqual(attributes["availability"], "IN_STOCK")
        self.assertEqual(attributes["condition"], "NEW")
        self.assertEqual(attributes["gtins"], ["8592978652883"])
        self.assertEqual(
            attributes["price"],
            {"amountMicros": "18997000000", "currencyCode": "EUR"},
        )
        self.assertEqual(check_public_url.call_count, 2)
        configured_account.assert_called_once_with()
        merchant_get.assert_not_called()
        merchant_post.assert_not_called()

    @patch.object(MERCHANT, "_merchant_post", return_value={"name": "dry-run"})
    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_upsert_uses_preflight_price_payload_without_real_publication(
        self,
        _configured_account,
        _check_public_url,
        merchant_post,
    ) -> None:
        result = MERCHANT.google_merchant_upsert_product(
            **real_product(),
            confirmation="PUBLICAR_EN_GOOGLE_MERCHANT",
        )

        self.assertTrue(result["preflight"]["ok"])
        merchant_post.assert_called_once()
        call = merchant_post.call_args
        self.assertEqual(
            call.kwargs["json_data"]["productAttributes"]["price"],
            {"amountMicros": "18997000000", "currencyCode": "EUR"},
        )

    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_supported_availability_spellings_are_normalized(
        self,
        _configured_account,
        _check_public_url,
    ) -> None:
        for value in ("in-stock", "IN_STOCK", "https://schema.org/InStock"):
            with self.subTest(value=value):
                result = MERCHANT.google_merchant_preflight_product(
                    **real_product(
                        availability=value,
                        public_availability=value,
                    )
                )

                self.assertTrue(result["ok"], result)
                self.assertEqual(
                    result["normalized"]["payload"]["productAttributes"][
                        "availability"
                    ],
                    "IN_STOCK",
                )

    @patch.object(MERCHANT, "_check_public_url")
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_validation_error_is_structured_and_skips_http(
        self,
        _configured_account,
        check_public_url,
    ) -> None:
        result = MERCHANT.google_merchant_preflight_product(
            **real_product(availability="available")
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], ["availability no es válido"])
        self.assertIsNone(result["normalized"])
        check_public_url.assert_not_called()

    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_only_signature_required_parameters_return_structured_errors(
        self,
        _configured_account,
    ) -> None:
        required = real_product()

        for optional in (
            "gtin",
            "currency_code",
            "content_language",
            "feed_label",
            "condition",
            "public_price",
            "public_currency",
            "public_availability",
        ):
            required.pop(optional)

        result = MERCHANT.google_merchant_preflight_product(**required)

        self.assertFalse(result["ok"])
        self.assertTrue(result["errors"])
        self.assertNotIn("diagnostic", result)

    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_price_currency_and_availability_mismatches_are_reported(
        self,
        _configured_account,
        _check_public_url,
    ) -> None:
        result = MERCHANT.google_merchant_preflight_product(
            **real_product(
                public_price=18997.01,
                public_currency="USD",
                public_availability="out-of-stock",
            )
        )

        self.assertFalse(result["ok"])
        self.assertEqual(len(result["errors"]), 3)
        self.assertTrue(any("precio" in error for error in result["errors"]))
        self.assertTrue(any("moneda" in error for error in result["errors"]))
        self.assertTrue(
            any("disponibilidad" in error for error in result["errors"])
        )

    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_non_finite_public_price_is_a_validation_error(
        self,
        _configured_account,
        _check_public_url,
    ) -> None:
        result = MERCHANT.google_merchant_preflight_product(
            **real_product(public_price=float("nan"))
        )

        self.assertFalse(result["ok"])
        self.assertIn(
            "El precio público observado no es válido",
            result["errors"],
        )

    @patch.object(MERCHANT, "_product_preflight")
    def test_unexpected_exception_keeps_sanitized_diagnostic(
        self,
        product_preflight,
    ) -> None:
        product_preflight.side_effect = RuntimeError(
            "access_token=secret-value failed"
        )

        result = MERCHANT.google_merchant_preflight_product(**real_product())

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["diagnostic"]["exception_type"],
            "RuntimeError",
        )
        self.assertIn("[REDACTED]", result["diagnostic"]["message"])
        self.assertNotIn("secret-value", result["diagnostic"]["message"])


class GoogleMerchantMcpTransportRegressionTests(
    unittest.IsolatedAsyncioTestCase
):
    @patch.object(MERCHANT, "_merchant_post")
    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    async def test_mcp_transport_preserves_large_price(
        self,
        _configured_account,
        _check_public_url,
        merchant_post,
    ) -> None:
        result = await MERCHANT.mcp.call_tool(
            "google_merchant_preflight_product",
            real_product(),
        )

        preflight = result.structured_content
        self.assertTrue(preflight["ok"])
        self.assertEqual(preflight["errors"], [])
        self.assertEqual(
            preflight["normalized"]["payload"]["productAttributes"]["price"],
            {"amountMicros": "18997000000", "currencyCode": "EUR"},
        )
        merchant_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
