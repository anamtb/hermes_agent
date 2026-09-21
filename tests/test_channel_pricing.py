import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "mcp" / "commerce" / "pricing.py"
SPEC = importlib.util.spec_from_file_location("channel_pricing", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar pricing")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ChannelPricingTests(unittest.TestCase):
    def test_channel_fees_are_included(self):
        result = MODULE.calculate_channel_pricing_scenarios(
            base_cost=100,
            shipping_cost=10,
            channel_fixed_fee=2,
            channel_percent_fee=0.10,
            other_channel_costs=5,
            tax_rate=0.21,
        )

        self.assertEqual(result["price_floor"]["net_price"], 130.0)
        self.assertEqual(result["profit_status"], "DEFINITIVE")

    def test_unknown_fee_blocks_definitive_profit(self):
        result = MODULE.calculate_channel_pricing_scenarios(
            base_cost=100,
            tax_rate=0.21,
        )

        self.assertEqual(result["channel_cost_inputs"]["channel_fixed_fee"], "UNKNOWN")
        self.assertEqual(result["profit_status"], "UNKNOWN")
        self.assertEqual(
            result["scenarios"]["moderate"]["definitive_unit_profit"],
            "UNKNOWN",
        )


if __name__ == "__main__":
    unittest.main()
