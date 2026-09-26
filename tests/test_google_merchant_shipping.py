import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mcp" / "google-merchant" / "google_merchant_mcp.py"
MODULE_DIR = str(MODULE_PATH.parent)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

SPEC = importlib.util.spec_from_file_location("google_merchant_shipping_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar Google Merchant MCP")
MERCHANT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERCHANT)

def shipping_arguments(**overrides):
    values = {
        "country_code": "ES",
        "service_name": "Envío peninsular",
        "currency_code": "EUR",
        "shipping_type": "FREE",
        "min_handling_days": 0,
        "max_handling_days": 1,
        "min_transit_days": 1,
        "max_transit_days": 3,
    }
    values.update(overrides)
    return values


def current_settings():
    return {
        "name": "accounts/1/shippingSettings",
        "etag": "etag-current",
        "services": [
            {
                "serviceName": "Servicio existente",
                "active": True,
                "deliveryCountries": ["FR"],
                "currencyCode": "EUR",
            }
        ],
        "warehouses": [{"name": "warehouse-existing"}],
    }


class ShippingPolicyHelperTests(unittest.TestCase):
    def test_free_shipping_uses_zero_micros(self):
        service = MERCHANT.build_shipping_service(**shipping_arguments())

        self.assertEqual(
            service["rateGroups"][0]["singleValue"]["flatRate"],
            {"amountMicros": "0", "currencyCode": "EUR"},
        )

    def test_flat_rate_is_validated_and_converted(self):
        service = MERCHANT.build_shipping_service(
            **shipping_arguments(shipping_type="FLAT_RATE", flat_rate="4.95")
        )

        self.assertEqual(
            service["rateGroups"][0]["singleValue"]["flatRate"]["amountMicros"],
            "4950000",
        )

    def test_invalid_shipping_inputs_are_rejected(self):
        invalid = (
            {"country_code": "ESP"},
            {"shipping_type": "ESTIMATE"},
            {"min_transit_days": 4, "max_transit_days": 2},
            {"shipping_type": "FREE", "flat_rate": 1},
            {"shipping_type": "FLAT_RATE", "flat_rate": None},
        )

        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                MERCHANT.build_shipping_service(**shipping_arguments(**overrides))

    def test_merge_changes_only_named_service(self):
        existing = current_settings()["services"]
        replacement = MERCHANT.build_shipping_service(**shipping_arguments())
        merged, previous = MERCHANT.merge_service(existing, replacement)

        self.assertEqual(merged[0], existing[0])
        self.assertIsNone(previous)
        self.assertEqual(merged[1]["serviceName"], "Envío peninsular")
        self.assertEqual(len(existing), 1, "merge_service no debe mutar el original")


class ShippingPolicyMcpTests(unittest.TestCase):
    @patch.object(MERCHANT, "_merchant_post")
    @patch.object(MERCHANT, "_fetch_shipping_settings", side_effect=lambda _: current_settings())
    @patch.object(MERCHANT, "_configured_account_id", return_value="1")
    def test_prepare_is_read_only_and_preserves_full_resource(
        self,
        _account,
        _fetch,
        merchant_post,
    ):
        result = MERCHANT.google_merchant_prepare_shipping_policy(
            **shipping_arguments()
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["write_performed"])
        self.assertEqual(result["current_etag"], "etag-current")
        self.assertEqual(
            result["proposed_resource"]["warehouses"],
            [{"name": "warehouse-existing"}],
        )
        self.assertEqual(len(result["proposed_resource"]["services"]), 2)
        merchant_post.assert_not_called()

    @patch.object(MERCHANT, "_set_shipping_policy")
    def test_set_requires_exact_confirmation_before_any_write(self, setter):
        result = MERCHANT.google_merchant_set_shipping_policy(
            **shipping_arguments(),
            expected_etag="etag-current",
            confirmation="",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "confirmation_required")
        setter.assert_not_called()

    @patch.object(MERCHANT, "_merchant_post")
    @patch.object(MERCHANT, "_fetch_shipping_settings", side_effect=lambda _: current_settings())
    @patch.object(MERCHANT, "_configured_account_id", return_value="1")
    def test_etag_mismatch_blocks_write(self, _account, _fetch, merchant_post):
        result = MERCHANT.google_merchant_set_shipping_policy(
            **shipping_arguments(),
            expected_etag="etag-old",
            confirmation=MERCHANT.SHIPPING_CONFIRMATION,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["conflict"])
        merchant_post.assert_not_called()

    @patch.object(
        MERCHANT,
        "_merchant_post",
        return_value={"etag": "etag-new"},
    )
    @patch.object(MERCHANT, "_fetch_shipping_settings", side_effect=lambda _: current_settings())
    @patch.object(MERCHANT, "_configured_account_id", return_value="1")
    def test_approved_write_posts_complete_resource(
        self,
        _account,
        _fetch,
        merchant_post,
    ):
        result = MERCHANT.google_merchant_set_shipping_policy(
            **shipping_arguments(),
            expected_etag="etag-current",
            confirmation=MERCHANT.SHIPPING_CONFIRMATION,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        merchant_post.assert_called_once()
        call = merchant_post.call_args
        self.assertEqual(
            call.args[0],
            "/accounts/v1/accounts/1/shippingSettings:insert",
        )
        body = call.kwargs["json_data"]
        self.assertEqual(body["etag"], "etag-current")
        self.assertEqual(body["warehouses"], [{"name": "warehouse-existing"}])
        self.assertEqual(len(body["services"]), 2)

    def test_set_tool_schema_requires_gate_and_etag(self):
        tool = MERCHANT.mcp._tool_manager.get_tool(
            "google_merchant_set_shipping_policy"
        )
        required = set(tool.parameters["required"])
        self.assertIn("confirmation", required)
        self.assertIn("expected_etag", required)


if __name__ == "__main__":
    unittest.main()
