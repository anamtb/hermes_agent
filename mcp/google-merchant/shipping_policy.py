"""Pure validation and preparation helpers for Google Merchant shipping settings.

No network calls happen here; the MCP layer performs all HTTP I/O. Every
function is deterministic and safe to unit test in isolation.
"""

from __future__ import annotations

import re
from copy import deepcopy
from decimal import Decimal
from typing import Any

from product_validation import (
    MICROS_PER_CURRENCY_UNIT,
    normalize_currency_code,
    price_to_amount_micros,
)


SHIPPING_TYPES = {"FREE", "FLAT_RATE"}
# Sanity ceiling to catch typos (for example days=9999); Merchant itself
# allows larger values, this is only a defensive guard, not a business rule.
MAX_DAYS = 90


def normalize_country_code(value: str) -> str:
    normalized = value.strip().upper()

    if not re.fullmatch(r"[A-Z]{2}", normalized):
        raise ValueError(
            "country_code debe ser un código de país ISO 3166-1 alpha-2"
        )

    return normalized


def normalize_service_name(value: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError("service_name es obligatorio")

    return normalized


def normalize_shipping_type(value: str) -> str:
    normalized = value.strip().upper()

    if normalized not in SHIPPING_TYPES:
        raise ValueError("shipping_type debe ser FREE o FLAT_RATE")

    return normalized


def _validate_day_range(
    min_days: int,
    max_days: int,
    *,
    field_label: str,
) -> tuple[int, int]:
    for name, value in (
        (f"min_{field_label}_days", min_days),
        (f"max_{field_label}_days", max_days),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} debe ser un entero")

        if value < 0:
            raise ValueError(f"{name} no puede ser negativo")

        if value > MAX_DAYS:
            raise ValueError(
                f"{name} supera el máximo razonable ({MAX_DAYS} días)"
            )

    if max_days < min_days:
        raise ValueError(
            f"max_{field_label}_days debe ser mayor o igual que "
            f"min_{field_label}_days"
        )

    return min_days, max_days


def build_shipping_price(
    amount: Decimal | int | float | str,
    currency_code: str,
) -> dict[str, str]:
    """Build a Merchant API ``Price`` object, allowing a zero amount."""

    return {
        "amountMicros": str(price_to_amount_micros(amount, allow_zero=True)),
        "currencyCode": normalize_currency_code(currency_code),
    }


def build_shipping_service(
    *,
    service_name: str,
    country_code: str,
    currency_code: str,
    shipping_type: str,
    min_handling_days: int,
    max_handling_days: int,
    min_transit_days: int,
    max_transit_days: int,
    flat_rate: Decimal | int | float | str | None = None,
    active: bool = True,
) -> dict[str, Any]:
    """Validate inputs and build one Merchant API ``Service`` object."""

    normalized_service_name = normalize_service_name(service_name)
    normalized_country = normalize_country_code(country_code)
    normalized_currency = normalize_currency_code(currency_code)
    normalized_type = normalize_shipping_type(shipping_type)

    handling_min, handling_max = _validate_day_range(
        min_handling_days,
        max_handling_days,
        field_label="handling",
    )
    transit_min, transit_max = _validate_day_range(
        min_transit_days,
        max_transit_days,
        field_label="transit",
    )

    if normalized_type == "FREE":
        if flat_rate is not None:
            raise ValueError(
                "flat_rate no debe indicarse cuando shipping_type es FREE"
            )

        rate_amount: Decimal | int | float | str = 0
    else:
        if flat_rate is None:
            raise ValueError(
                "flat_rate es obligatorio cuando shipping_type es FLAT_RATE"
            )

        rate_amount = flat_rate

    flat_rate_price = build_shipping_price(rate_amount, normalized_currency)

    if normalized_type == "FLAT_RATE" and Decimal(
        flat_rate_price["amountMicros"]
    ) <= 0:
        raise ValueError("flat_rate debe ser mayor que cero para FLAT_RATE")

    return {
        "serviceName": normalized_service_name,
        "active": bool(active),
        "deliveryCountries": [normalized_country],
        "currencyCode": normalized_currency,
        "deliveryTime": {
            "minHandlingDays": handling_min,
            "maxHandlingDays": handling_max,
            "minTransitDays": transit_min,
            "maxTransitDays": transit_max,
        },
        "rateGroups": [
            {
                "singleValue": {
                    "flatRate": flat_rate_price,
                },
            }
        ],
    }


def merge_service(
    current_services: list[dict[str, Any]] | None,
    new_service: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Merge ``new_service`` into ``current_services`` by ``serviceName``.

    Every other existing service is preserved untouched. Returns the merged
    list and the previous version of the target service, or ``None`` when it
    did not exist yet.
    """

    services = deepcopy(current_services) if current_services else []
    target_name = new_service["serviceName"]

    for index, service in enumerate(services):
        if service.get("serviceName") == target_name:
            previous = deepcopy(service)
            services[index] = deepcopy(new_service)
            return services, previous

    services.append(deepcopy(new_service))
    return services, None


def describe_service_diff(
    previous_service: dict[str, Any] | None,
    new_service: dict[str, Any],
) -> dict[str, Any]:
    """Build a human-reviewable diff between the previous and new service."""

    if previous_service is None:
        return {
            "action": "create",
            "before": None,
            "after": deepcopy(new_service),
            "changed_fields": sorted(new_service.keys()),
        }

    changed_fields = sorted(
        key
        for key in set(previous_service) | set(new_service)
        if previous_service.get(key) != new_service.get(key)
    )

    return {
        "action": "update" if changed_fields else "unchanged",
        "before": deepcopy(previous_service),
        "after": deepcopy(new_service),
        "changed_fields": changed_fields,
    }


def summarize_service(service: dict[str, Any]) -> str:
    """Render a short human-readable summary of a shipping service."""

    delivery_time = service.get("deliveryTime") or {}
    rate_groups = service.get("rateGroups") or []
    single_value = (rate_groups[0].get("singleValue") if rate_groups else None) or {}
    flat_rate = single_value.get("flatRate")

    if flat_rate and Decimal(str(flat_rate.get("amountMicros", "0"))) == 0:
        price_text = f"envío gratis ({flat_rate.get('currencyCode')})"
    elif flat_rate:
        amount = Decimal(str(flat_rate["amountMicros"])) / MICROS_PER_CURRENCY_UNIT
        price_text = f"tarifa fija {amount} {flat_rate.get('currencyCode')}"
    else:
        price_text = "tarifa no definida"

    countries = ", ".join(service.get("deliveryCountries") or [])
    status = "activo" if service.get("active") else "inactivo"

    return (
        f"Servicio '{service.get('serviceName')}' ({status}) a {countries}: "
        f"{price_text}; preparación "
        f"{delivery_time.get('minHandlingDays')}-{delivery_time.get('maxHandlingDays')} "
        f"días, tránsito "
        f"{delivery_time.get('minTransitDays')}-{delivery_time.get('maxTransitDays')} días."
    )
