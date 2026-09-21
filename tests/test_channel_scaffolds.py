import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, relative_path):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AMAZON = load("amazon_scaffold_test", "mcp/amazon/amazon_mcp.py")
PCCOMPONENTES = load(
    "pccomponentes_scaffold_test",
    "mcp/pccomponentes/pccomponentes_mcp.py",
)


class ChannelScaffoldTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_amazon_is_truthful_and_offline(self):
        result = AMAZON.amazon_get_capabilities()
        self.assertEqual(result["implementation_status"], "SCAFFOLDED")
        self.assertFalse(result["configured"])
        self.assertFalse(result["network_request_performed"])
        self.assertFalse(result["capabilities"]["supports_catalog_publish"])

    @patch.dict(os.environ, {}, clear=True)
    def test_pccomponentes_is_truthful_and_offline(self):
        result = PCCOMPONENTES.pccomponentes_get_capabilities()
        self.assertEqual(result["implementation_status"], "SCAFFOLDED")
        self.assertFalse(result["configured"])
        self.assertFalse(result["network_request_performed"])
        self.assertFalse(result["capabilities"]["supports_offer_publish"])


if __name__ == "__main__":
    unittest.main()
