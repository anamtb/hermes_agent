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

SPEC = importlib.util.spec_from_file_location("google_channel_adapter_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar Google Merchant MCP")
MERCHANT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERCHANT)


class GoogleChannelAdapterTests(unittest.TestCase):
    @patch.object(MERCHANT, "_merchant_get")
    @patch.object(MERCHANT, "_merchant_post")
    def test_capabilities_are_offline_and_implemented(self, post, get):
        result = MERCHANT.google_merchant_get_capabilities()

        self.assertEqual(result["implementation_status"], "IMPLEMENTED")
        self.assertTrue(result["capabilities"]["supports_catalog_publish"])
        self.assertTrue(result["capabilities"]["supports_shipping_policy"])
        self.assertFalse(result["network_request_performed"])
        get.assert_not_called()
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
