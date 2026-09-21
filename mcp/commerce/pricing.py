"""Pure, reusable pricing calculations for commerce launch workflows."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")


def _decimal(name: str, value: float | int | str | None) -> Decimal | None:
    if value is None:
        return None

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} debe ser numérico") from exc

    if not result.is_finite():
        raise ValueError(f"{name} debe ser finito")

    return result


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def _percent(value: Decimal) -> float:
    return float(value.quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP))


def calculate_pricing_scenarios(
    *,
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
    """Return an explainable price floor and three customer-price scenarios.

    ``tax_rate`` and ``channel_fee_percent`` are decimal rates (for example,
    ``0.21`` and ``0.15``). Market prices are gross customer prices. The
    percentage channel fee is applied to the net selling price. Missing
    optional costs are provisionally treated as zero and reported explicitly.
    """

    purchase = _decimal("purchase_cost", purchase_cost)
    tax = _decimal("tax_rate", tax_rate)

    if purchase is None or purchase <= 0:
        raise ValueError("purchase_cost debe ser mayor que cero")

    if tax is None or tax < 0 or tax > 1:
        raise ValueError("tax_rate debe estar entre 0 y 1")

    optional_cost_inputs = {
        "shipping_cost": shipping_cost,
        "other_unit_costs": other_unit_costs,
        "channel_fee_fixed": channel_fee_fixed,
        "channel_fee_percent": channel_fee_percent,
    }
    missing_costs = [
        name for name, value in optional_cost_inputs.items() if value is None
    ]

    shipping = _decimal("shipping_cost", shipping_cost) or Decimal("0")
    other = _decimal("other_unit_costs", other_unit_costs) or Decimal("0")
    fee_fixed = (
        _decimal("channel_fee_fixed", channel_fee_fixed) or Decimal("0")
    )
    fee_percent = (
        _decimal("channel_fee_percent", channel_fee_percent)
        or Decimal("0")
    )

    for name, value in {
        "shipping_cost": shipping,
        "other_unit_costs": other,
        "channel_fee_fixed": fee_fixed,
    }.items():
        if value < 0:
            raise ValueError(f"{name} no puede ser negativo")

    if fee_percent < 0 or fee_percent >= 1:
        raise ValueError(
            "channel_fee_percent debe ser mayor o igual que 0 y menor que 1"
        )

    market_values = {
        "market_low": _decimal("market_low", market_low),
        "market_median": _decimal("market_median", market_median),
        "market_high": _decimal("market_high", market_high),
    }

    for name, value in market_values.items():
        if value is not None and value <= 0:
            raise ValueError(f"{name} debe ser mayor que cero")

    known_costs = purchase + shipping + other + fee_fixed
    floor_net = known_costs / (Decimal("1") - fee_percent)
    floor_tax = floor_net * tax
    floor_gross = floor_net + floor_tax

    scenario_targets = {
        "conservative": (
            market_values["market_low"] or floor_gross * Decimal("1.05"),
            "market_low" if market_values["market_low"] else "floor_plus_5pct",
        ),
        "moderate": (
            market_values["market_median"] or floor_gross * Decimal("1.15"),
            (
                "market_median"
                if market_values["market_median"]
                else "floor_plus_15pct"
            ),
        ),
        "aggressive": (
            market_values["market_high"] or floor_gross * Decimal("1.30"),
            "market_high" if market_values["market_high"] else "floor_plus_30pct",
        ),
    }

    scenarios: dict[str, dict[str, Any]] = {}

    for name, (target_gross, source) in scenario_targets.items():
        below_floor = target_gross < floor_gross
        gross = (
            target_gross
            if allow_below_floor or not below_floor
            else floor_gross
        )
        net = gross / (Decimal("1") + tax)
        tax_amount = gross - net
        variable_fee = net * fee_percent
        total_cost = purchase + shipping + other + fee_fixed + variable_fee
        profit = net - total_cost
        margin = (profit / net * Decimal("100")) if net else Decimal("0")

        scenarios[name] = {
            "net_price": _money(net),
            "tax": _money(tax_amount),
            "gross_price": _money(gross),
            "purchase_cost": _money(purchase),
            "shipping_cost": _money(shipping),
            "other_unit_costs": _money(other),
            "channel_fee_fixed": _money(fee_fixed),
            "channel_fee_percent": _percent(fee_percent * Decimal("100")),
            "channel_fee_amount": _money(variable_fee),
            "total_cost": _money(total_cost),
            "unit_profit": _money(profit),
            "gross_margin_percent": _percent(margin),
            "market_basis": source,
            "clamped_to_price_floor": below_floor and not allow_below_floor,
            "below_price_floor": gross < floor_gross,
        }

    return {
        "price_floor": {
            "net_price": _money(floor_net),
            "tax": _money(floor_tax),
            "gross_price": _money(floor_gross),
            "currency": "caller_supplied",
            "provisional": bool(missing_costs),
        },
        "scenarios": scenarios,
        "missing_cost_inputs": missing_costs,
        "costs_complete": not missing_costs,
        "allow_below_floor": allow_below_floor,
        "method": {
            "market_prices_include_tax": True,
            "channel_fee_percent_applies_to": "net_price",
            "missing_optional_costs_treated_as_zero": True,
        },
    }


def calculate_channel_pricing_scenarios(
    *,
    base_cost: float,
    tax_rate: float,
    shipping_cost: float | None = None,
    channel_fixed_fee: float | None = None,
    channel_percent_fee: float | None = None,
    other_channel_costs: float | None = None,
    market_low: float | None = None,
    market_median: float | None = None,
    market_high: float | None = None,
    allow_below_floor: bool = False,
) -> dict[str, Any]:
    """Channel-named facade over the stable pricing implementation.

    Unknown inputs remain explicit. Calculated figures are useful scenarios,
    but profit is not labelled definitive until every channel cost is known.
    """

    result = calculate_pricing_scenarios(
        purchase_cost=base_cost,
        tax_rate=tax_rate,
        shipping_cost=shipping_cost,
        other_unit_costs=other_channel_costs,
        channel_fee_fixed=channel_fixed_fee,
        channel_fee_percent=channel_percent_fee,
        market_low=market_low,
        market_median=market_median,
        market_high=market_high,
        allow_below_floor=allow_below_floor,
    )
    result["channel_cost_inputs"] = {
        "base_cost": base_cost,
        "shipping_cost": shipping_cost if shipping_cost is not None else "UNKNOWN",
        "channel_fixed_fee": (
            channel_fixed_fee if channel_fixed_fee is not None else "UNKNOWN"
        ),
        "channel_percent_fee": (
            channel_percent_fee if channel_percent_fee is not None else "UNKNOWN"
        ),
        "other_channel_costs": (
            other_channel_costs if other_channel_costs is not None else "UNKNOWN"
        ),
    }
    result["profit_status"] = "DEFINITIVE" if result["costs_complete"] else "UNKNOWN"
    for scenario in result["scenarios"].values():
        scenario["definitive_unit_profit"] = (
            scenario["unit_profit"] if result["costs_complete"] else "UNKNOWN"
        )
        scenario["definitive_gross_margin_percent"] = (
            scenario["gross_margin_percent"]
            if result["costs_complete"]
            else "UNKNOWN"
        )
    return result
