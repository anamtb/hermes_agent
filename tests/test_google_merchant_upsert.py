import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mcp" / "google-merchant" / "google_merchant_mcp.py"
MODULE_DIR = str(MODULE_PATH.parent)

if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

SPEC = importlib.util.spec_from_file_location(
    "google_merchant_upsert_regression",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar google_merchant_mcp")

MERCHANT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERCHANT)


def product_arguments(**overrides):
    values = {
        "data_source_id": "7890",
        "offer_id": "TEST-SKU",
        "title": "Producto de prueba",
        "description": "Descripción verificable del producto de prueba",
        "link": "https://shop.example/products/test-sku",
        "image_link": "https://shop.example/images/test-sku.jpg",
        "price_eur": 18997,
        "currency_code": "EUR",
        "availability": "IN_STOCK",
        "condition": "NEW",
        "brand": "Example",
        "mpn": "MPN-TEST",
        "content_language": "es",
        "feed_label": "ES",
        "public_price": 18997,
        "public_currency": "EUR",
        "public_availability": "IN_STOCK",
        "confirmation": "PUBLICAR_EN_GOOGLE_MERCHANT",
        "gtin": None,
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


def google_error_response(status_code: int) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={
            "error": {
                "code": status_code,
                "status": f"STATUS_{status_code}",
                "message": f"Google detail for {status_code}",
                "details": [{"reason": f"reason-{status_code}"}],
            }
        },
    )


class GoogleMerchantHttpTests(unittest.TestCase):
    def call_merchant_post_with_response(
        self,
        response: httpx.Response,
    ):
        with (
            patch.object(MERCHANT.httpx, "Client") as client_class,
            patch.object(
                MERCHANT,
                "_get_access_token",
                return_value="test-access-token",
            ),
        ):
            client = client_class.return_value.__enter__.return_value
            client.post.return_value = response

            result = MERCHANT._merchant_post(
                "/products/v1/accounts/123456/productInputs:insert",
                params={
                    "dataSource": "accounts/123456/dataSources/7890",
                },
                json_data={"offerId": "TEST-SKU"},
            )
            return result, client.post.call_args

    def test_200_and_201_are_successful(self) -> None:
        for status_code in (200, 201):
            with self.subTest(status_code=status_code):
                response = httpx.Response(
                    status_code,
                    json={"offerId": "TEST-SKU"},
                )
                result, post_call = self.call_merchant_post_with_response(
                    response
                )

                self.assertEqual(result, {"offerId": "TEST-SKU"})
                self.assertEqual(
                    post_call.args,
                    (
                        (
                            "https://merchantapi.googleapis.com/products/v1/"
                            "accounts/123456/productInputs:insert"
                        ),
                    ),
                )
                self.assertEqual(
                    post_call.kwargs,
                    {
                        "params": {
                            "dataSource": (
                                "accounts/123456/dataSources/7890"
                            ),
                        },
                        "json": {"offerId": "TEST-SKU"},
                        "headers": {
                            "Authorization": "Bearer test-access-token",
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                    },
                )

    def test_http_errors_are_classified_with_google_details(self) -> None:
        cases = (
            (400, "invalid_request"),
            (401, "oauth_authentication"),
            (403, "permission_denied"),
            (404, "not_found"),
            (409, "conflict"),
            (429, "rate_limited"),
            (500, "temporary_google_error"),
            (503, "temporary_google_error"),
        )

        for status_code, expected_category in cases:
            with self.subTest(status_code=status_code):
                with self.assertRaises(MERCHANT.MerchantApiError) as caught:
                    self.call_merchant_post_with_response(
                        google_error_response(status_code)
                    )

                error = caught.exception.as_dict()
                self.assertEqual(error["status_code"], status_code)
                self.assertEqual(error["category"], expected_category)
                self.assertEqual(
                    error["google_message"],
                    f"Google detail for {status_code}",
                )

    def test_error_details_and_oauth_secrets_are_redacted(self) -> None:
        response = httpx.Response(
            401,
            json={
                "error": {
                    "status": "UNAUTHENTICATED",
                    "message": "access_token=secret-token-value is invalid",
                    "details": [
                        {
                            "client_secret": "secret-client-value",
                            "refresh_token": "secret-refresh-value",
                            "accessToken": "secret-camelcase-value",
                        }
                    ],
                }
            },
        )

        with self.assertRaises(MERCHANT.MerchantApiError) as caught:
            self.call_merchant_post_with_response(response)

        serialized_error = str(caught.exception.as_dict())
        self.assertNotIn("secret-token-value", serialized_error)
        self.assertNotIn("secret-client-value", serialized_error)
        self.assertNotIn("secret-refresh-value", serialized_error)
        self.assertNotIn("secret-camelcase-value", serialized_error)
        self.assertIn("[REDACTED]", serialized_error)

    @patch.object(MERCHANT.httpx, "Client")
    @patch.object(
        MERCHANT,
        "_get_access_token",
        side_effect=RuntimeError("refresh_token=secret-refresh-value"),
    )
    def test_oauth_token_failure_is_controlled_and_redacted(
        self,
        _get_access_token,
        client_class,
    ) -> None:
        with self.assertRaises(MERCHANT.MerchantApiError) as caught:
            MERCHANT._merchant_post(
                "/products/v1/accounts/123/productInputs:insert"
            )

        error = caught.exception.as_dict()
        self.assertEqual(error["category"], "oauth_token")
        self.assertNotIn("secret-refresh-value", str(error))
        client_class.assert_not_called()

    @patch.object(MERCHANT.httpx, "Client")
    @patch.object(
        MERCHANT,
        "_get_access_token",
        return_value="test-access-token",
    )
    def test_network_failure_is_controlled(
        self,
        _get_access_token,
        client_class,
    ) -> None:
        client = client_class.return_value.__enter__.return_value
        client.post.side_effect = httpx.ConnectError("connection failed")

        with self.assertRaises(MERCHANT.MerchantApiError) as caught:
            MERCHANT._merchant_post(
                "/products/v1/accounts/123/productInputs:insert"
            )

        self.assertEqual(caught.exception.category, "network_error")
        self.assertIn("Google Merchant API", str(caught.exception))


class GoogleMerchantUpsertTests(unittest.TestCase):
    @patch.object(MERCHANT, "_merchant_post", return_value={"name": "saved"})
    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    def test_upsert_sends_normalized_product_input_for_18997(
        self,
        _configured_account,
        _check_public_url,
        merchant_post,
    ) -> None:
        result = MERCHANT.google_merchant_upsert_product(**product_arguments())

        self.assertTrue(result["ok"])
        self.assertTrue(result["submitted"])
        merchant_post.assert_called_once()
        call = merchant_post.call_args
        self.assertEqual(
            call.args[0],
            "/products/v1/accounts/123456/productInputs:insert",
        )
        self.assertEqual(
            call.kwargs["params"],
            {"dataSource": "accounts/123456/dataSources/7890"},
        )
        self.assertEqual(
            call.kwargs["json_data"],
            {
                "offerId": "TEST-SKU",
                "contentLanguage": "es",
                "feedLabel": "ES",
                "productAttributes": {
                    "title": "Producto de prueba",
                    "description": (
                        "Descripción verificable del producto de prueba"
                    ),
                    "link": "https://shop.example/products/test-sku",
                    "imageLink": "https://shop.example/images/test-sku.jpg",
                    "availability": "IN_STOCK",
                    "condition": "NEW",
                    "brand": "Example",
                    "mpn": "MPN-TEST",
                    "price": {
                        "amountMicros": "18997000000",
                        "currencyCode": "EUR",
                    },
                },
            },
        )

    def test_upsert_schema_requires_all_preflight_inputs(self) -> None:
        tool = MERCHANT.mcp._tool_manager.get_tool(
            "google_merchant_upsert_product"
        )
        required = set(tool.parameters["required"])

        self.assertTrue(
            {
                "currency_code",
                "condition",
                "content_language",
                "feed_label",
                "public_price",
                "public_currency",
                "public_availability",
                "confirmation",
            }.issubset(required)
        )


class GoogleMerchantUpsertMcpTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(
        MERCHANT,
        "_merchant_post",
        side_effect=RuntimeError("client_secret=must-not-leak"),
    )
    @patch.object(MERCHANT, "_check_public_url", side_effect=successful_url_check)
    @patch.object(MERCHANT, "_configured_account_id", return_value="123456")
    async def test_unexpected_upsert_error_is_structured_and_mcp_stays_alive(
        self,
        _configured_account,
        _check_public_url,
        _merchant_post,
    ) -> None:
        failed = await MERCHANT.mcp.call_tool(
            "google_merchant_upsert_product",
            product_arguments(),
        )
        failure = failed.structured_content

        self.assertFalse(failure["ok"])
        self.assertFalse(failure["submitted"])
        self.assertEqual(
            failure["error"]["category"],
            "unexpected_exception",
        )
        self.assertNotIn("must-not-leak", str(failure))

        healthy = await MERCHANT.mcp.call_tool(
            "google_merchant_preflight_product",
            {
                key: value
                for key, value in product_arguments().items()
                if key != "confirmation"
            },
        )
        self.assertTrue(healthy.structured_content["ok"])


if __name__ == "__main__":
    unittest.main()
