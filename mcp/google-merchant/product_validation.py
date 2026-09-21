"""Pure validation helpers for Google Merchant product submissions."""

from __future__ import annotations

import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from hermes_commerce.channels.validation import (
        normalize_availability as _common_normalize_availability,
        normalize_condition as _common_normalize_condition,
        normalize_currency_code as _common_normalize_currency_code,
        validate_gtin as _common_validate_gtin,
        validate_https_url as _common_validate_https_url,
    )
except ModuleNotFoundError:
    # MCPs also support direct script execution from a profile checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from hermes_commerce.channels.validation import (
        normalize_availability as _common_normalize_availability,
        normalize_condition as _common_normalize_condition,
        normalize_currency_code as _common_normalize_currency_code,
        validate_gtin as _common_validate_gtin,
        validate_https_url as _common_validate_https_url,
    )


MICROS_PER_CURRENCY_UNIT = Decimal("1000000")
AMOUNT_MICROS_QUANTUM = Decimal("1")


def require_confirmation(value: str, expected: str) -> None:
    if value != expected:
        raise RuntimeError(
            "Publicación bloqueada. Se requiere confirmación explícita."
        )


def normalize_availability(value: str) -> str:
    return _common_normalize_availability(value)


def normalize_public_availability(value: str) -> str:
    return normalize_availability(value)


def normalize_condition(value: str) -> str:
    return _common_normalize_condition(value)


def validate_gtin(value: str) -> str:
    return _common_validate_gtin(value)


def validate_https_url(value: str, field_name: str) -> str:
    return _common_validate_https_url(value, field_name)


def normalize_currency_code(value: str, field_name: str = "currency_code") -> str:
    return _common_normalize_currency_code(value, field_name)


def product_resource_id(
    content_language: str,
    feed_label: str,
    offer_id: str,
) -> str:
    parts = [content_language.strip(), feed_label.strip(), offer_id.strip()]

    if not all(parts):
        raise ValueError(
            "content_language, feed_label y offer_id son obligatorios"
        )

    return quote("~".join(parts), safe="~")


def price_to_amount_micros(price: Decimal | int | float | str) -> int:
    """Convert a currency-unit price to Merchant API micros deterministically."""

    try:
        decimal_price = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("El precio debe ser numérico") from exc

    if not decimal_price.is_finite() or decimal_price <= 0:
        raise ValueError("El precio debe ser mayor que cero")

    try:
        return int(
            (decimal_price * MICROS_PER_CURRENCY_UNIT).quantize(
                AMOUNT_MICROS_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        )
    except InvalidOperation as exc:
        raise ValueError("El precio no se puede convertir a micros") from exc


def build_product_submission(
    *,
    account_id: str,
    data_source_id: str,
    offer_id: str,
    title: str,
    description: str,
    link: str,
    image_link: str,
    price: Decimal | int | float | str,
    currency_code: str,
    availability: str,
    condition: str,
    brand: str,
    mpn: str,
    content_language: str,
    feed_label: str,
    gtin: str | None = None,
) -> dict[str, Any]:
    account_id = account_id.strip()
    data_source_id = data_source_id.strip()
    offer_id = offer_id.strip()
    currency_code = normalize_currency_code(currency_code)
    content_language = content_language.strip()
    feed_label = feed_label.strip()
    condition = normalize_condition(condition)

    if not account_id.isdigit():
        raise ValueError("GOOGLE_MERCHANT_ACCOUNT_ID no es válido")

    if not data_source_id.isdigit():
        raise ValueError("data_source_id debe ser numérico")

    required_text = {
        "offer_id": offer_id,
        "title": title.strip(),
        "description": description.strip(),
        "brand": brand.strip(),
        "mpn": mpn.strip(),
        "content_language": content_language,
        "feed_label": feed_label,
    }

    for name, value in required_text.items():
        if not value:
            raise ValueError(f"{name} es obligatorio")

    normalized_link = validate_https_url(link, "link")
    normalized_image_link = validate_https_url(image_link, "image_link")

    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2})?", content_language):
        raise ValueError("content_language no es válido")

    normalized_availability = normalize_availability(availability)

    amount_micros = price_to_amount_micros(price)

    attributes: dict[str, Any] = {
        "title": required_text["title"],
        "description": required_text["description"],
        "link": normalized_link,
        "imageLink": normalized_image_link,
        "availability": normalized_availability,
        "condition": condition,
        "brand": required_text["brand"],
        "mpn": required_text["mpn"],
        "price": {
            "amountMicros": str(amount_micros),
            "currencyCode": currency_code,
        },
    }

    if gtin is not None and gtin.strip():
        attributes["gtins"] = [validate_gtin(gtin)]

    data_source_name = (
        f"accounts/{account_id}/dataSources/{data_source_id}"
    )

    return {
        "account_id": account_id,
        "data_source": data_source_name,
        "offer_id": offer_id,
        "product_id": product_resource_id(
            content_language,
            feed_label,
            offer_id,
        ),
        "payload": {
            "offerId": offer_id,
            "contentLanguage": content_language,
            "feedLabel": feed_label,
            "productAttributes": attributes,
        },
    }
