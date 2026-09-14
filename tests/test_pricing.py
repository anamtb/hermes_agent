import importlib.util
import unittest
from pathlib import Path


PRICING_PATH = (
    Path(__file__).resolve().parents[1]
    / "mcp"
    / "commerce"
    / "pricing.py"
)
SPEC = importlib.util.spec_from_file_location("commerce_pricing", PRICING_PATH)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No se pudo cargar el módulo de pricing")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
calculate_pricing_scenarios = MODULE.calculate_pricing_scenarios


class PricingTests(unittest.TestCase):
    def test_price_floor_covers_costs_and_fees(self) -> None:
        result = calculate_pricing_scenarios(
            purchase_cost=100,
            shipping_cost=10,
            other_unit_costs=5,
            channel_fee_fixed=2,
            channel_fee_percent=0.10,
            tax_rate=0.21,
        )

        self.assertAlmostEqual(result["price_floor"]["net_price"], 130.00)
        self.assertAlmostEqual(result["price_floor"]["gross_price"], 157.30)
        self.assertTrue(result["costs_complete"])

    def test_scenarios_are_clamped_to_floor(self) -> None:
        result = calculate_pricing_scenarios(
            purchase_cost=100,
            shipping_cost=0,
            other_unit_costs=0,
            channel_fee_fixed=0,
            channel_fee_percent=0,
            tax_rate=0.21,
            market_low=90,
            market_median=100,
            market_high=110,
        )

        for scenario in result["scenarios"].values():
            self.assertGreaterEqual(
                scenario["gross_price"],
                result["price_floor"]["gross_price"],
            )
            self.assertFalse(scenario["below_price_floor"])

    def test_explicit_loss_override_is_reported(self) -> None:
        result = calculate_pricing_scenarios(
            purchase_cost=100,
            shipping_cost=0,
            other_unit_costs=0,
            channel_fee_fixed=0,
            channel_fee_percent=0,
            tax_rate=0.21,
            market_low=90,
            market_median=100,
            market_high=110,
            allow_below_floor=True,
        )

        self.assertTrue(
            result["scenarios"]["conservative"]["below_price_floor"]
        )

    def test_missing_costs_are_not_silently_complete(self) -> None:
        result = calculate_pricing_scenarios(
            purchase_cost=100,
            tax_rate=0.21,
        )

        self.assertFalse(result["costs_complete"])
        self.assertIn("shipping_cost", result["missing_cost_inputs"])
        self.assertTrue(result["price_floor"]["provisional"])

    def test_invalid_fee_rate_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_pricing_scenarios(
                purchase_cost=100,
                tax_rate=0.21,
                channel_fee_percent=1,
            )

    def test_twenty_one_percent_tax_is_calculated_exactly(self) -> None:
        result = calculate_pricing_scenarios(
            purchase_cost=15000,
            shipping_cost=0,
            other_unit_costs=0,
            channel_fee_fixed=0,
            channel_fee_percent=0,
            tax_rate=0.21,
            market_low=18997,
            market_median=18997,
            market_high=18997,
        )

        scenario = result["scenarios"]["moderate"]
        self.assertEqual(scenario["net_price"], 15700.0)
        self.assertEqual(scenario["tax"], 3297.0)
        self.assertEqual(scenario["gross_price"], 18997.0)


if __name__ == "__main__":
    unittest.main()
