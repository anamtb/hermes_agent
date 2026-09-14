import importlib.util
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    module_dir = str(path.parent)

    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    spec = importlib.util.spec_from_file_location(name, path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ODOO = load_module(
    "odoo_mcp_safety_test",
    ROOT / "mcp" / "odoo" / "odoo_mcp.py",
)
MERCHANT = load_module(
    "merchant_mcp_safety_test",
    ROOT / "mcp" / "google-merchant" / "google_merchant_mcp.py",
)


class McpSafetyTests(unittest.TestCase):
    def test_odoo_publish_requires_explicit_confirmation(self) -> None:
        with self.assertRaises(RuntimeError):
            ODOO.odoo_publish_product(1)

    def test_odoo_cost_write_requires_explicit_confirmation(self) -> None:
        with self.assertRaises(RuntimeError):
            ODOO.odoo_set_product_cost(1, 100)

    def test_odoo_supplier_write_requires_explicit_confirmation(self) -> None:
        with self.assertRaises(RuntimeError):
            ODOO.odoo_set_product_supplier(1, 2, 100)

    def test_odoo_image_url_rejects_non_https(self) -> None:
        with self.assertRaises(ValueError):
            ODOO._validate_public_https_url("http://example.com/image.jpg")

    def test_odoo_image_url_rejects_loopback(self) -> None:
        with self.assertRaises(ValueError):
            ODOO._validate_public_https_url("https://127.0.0.1/image.jpg")

    def test_merchant_url_rejects_non_https(self) -> None:
        with self.assertRaises(ValueError):
            MERCHANT._validate_public_https_url("http://example.com/product")

    def test_merchant_url_rejects_loopback(self) -> None:
        with self.assertRaises(ValueError):
            MERCHANT._validate_public_https_url("https://127.0.0.1/product")

    @patch.object(MERCHANT.socket, "getaddrinfo")
    def test_merchant_url_rejects_private_dns_resolution(
        self,
        getaddrinfo,
    ) -> None:
        getaddrinfo.return_value = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.10.0.5", 443),
            )
        ]

        with self.assertRaises(ValueError):
            MERCHANT._validate_public_https_url(
                "https://shop.example/product"
            )

    @patch.object(MERCHANT, "_validate_public_https_url")
    @patch.object(MERCHANT.httpx, "Client")
    def test_merchant_httpx_failure_is_returned_as_url_check(
        self,
        client_class,
        _validate_url,
    ) -> None:
        client = client_class.return_value.__enter__.return_value
        client.stream.side_effect = MERCHANT.httpx.ConnectError(
            "connection failed"
        )

        result = MERCHANT._check_public_url(
            "https://shop.example/product",
            require_image=False,
        )

        self.assertFalse(result["public"])
        self.assertIn("connection failed", result["error"])


if __name__ == "__main__":
    unittest.main()
