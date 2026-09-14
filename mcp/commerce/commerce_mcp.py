from typing import Any

from mcp.server import MCPServer

from pricing import calculate_pricing_scenarios


mcp = MCPServer("commerce-pricing")


@mcp.tool()
def commerce_calculate_pricing(
    purchase_cost: float,
    tax_rate: float,
    shipping_cost: float | None = None,
    other_unit_costs: float | None = None,
    channel_fee_fixed: float | None = None,
    channel_fee_percent: float | None = None,
    market_low: float | None = None,
    market_median: float | None = None,
    market_high: float | None = None,
    allow_below_floor: bool = False,
) -> dict[str, Any]:
    """Calcula price floor y tres escenarios de precio reutilizables.

    Las tasas se expresan como decimal: 0.21 equivale al 21 %. Los precios
    de mercado son precios finales para el cliente, con impuestos incluidos.
    No autoriza ni modifica precios en Odoo o en ningún canal.
    """

    return calculate_pricing_scenarios(
        purchase_cost=purchase_cost,
        tax_rate=tax_rate,
        shipping_cost=shipping_cost,
        other_unit_costs=other_unit_costs,
        channel_fee_fixed=channel_fee_fixed,
        channel_fee_percent=channel_fee_percent,
        market_low=market_low,
        market_median=market_median,
        market_high=market_high,
        allow_below_floor=allow_below_floor,
    )


if __name__ == "__main__":
    mcp.run()
