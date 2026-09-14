"""Pure validation helpers for Google Merchant product submissions."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote, urlparse


GTIN_LENGTHS = {8, 12, 13, 14}
AVAILABILITY_ALIASES = {
    "instock": "IN_STOCK",
    "outofstock": "OUT_OF_STOCK",
    "preorder": "PREORDER",
    "backorder": "BACKORDER",
}
CONDITION_ALIASES = {
    "new": "NEW",
    "newcondition": "NEW",
    "refurbished": "REFURBISHED",
    "refurbishedcondition": "REFURBISHED",
    "used": "USED",
    "usedcondition": "USED",
}


def require_confirmation(value: str, expected: str) -> None:
    if value != expected:
        raise RuntimeError(
            "Publicación bloqueada. Se requiere confirmación explícita."
        )


def normalize_availability(value: str) -> str:
    normalized = value.strip().rstrip("/").rsplit("/", 1)[-1]
    alias = re.sub(r"[^a-z0-9]", "", normalized.lower())

    if alias not in AVAILABILITY_ALIASES:
        raise ValueError("availability no es válido")

    return AVAILABILITY_ALIASES[alias]


def normalize_public_availability(value: str) -> str:
    return normalize_availability(value)


def normalize_condition(value: str) -> str:
    normalized = value.strip().rstrip("/").rsplit("/", 1)[-1]
    alias = re.sub(r"[^a-z0-9]", "", normalized.lower())

    if alias not in CONDITION_ALIASES:
        raise ValueError("condition no es válido")

    return CONDITION_ALIASES[alias]


def validate_gtin(value: str) -> str:
    normalized = value.strip()

    if not normalized.isdigit() or len(normalized) not in GTIN_LENGTHS:
        raise ValueError("gtin debe tener 8, 12, 13 o 14 dígitos")

    body = normalized[:-1]
    weighted_sum = sum(
        int(digit) * (3 if (len(body) - index) % 2 else 1)
        for index, digit in enumerate(body)
    )
    expected_check_digit = (10 - weighted_sum % 10) % 10

    if int(normalized[-1]) != expected_check_digit:
        raise ValueError("gtin tiene un dígito de control no válido")

    return normalized


def validate_https_url(value: str, field_name: str) -> str:
    normalized = value.strip()

    try:
        parsed = urlparse(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} no es una URL válida") from exc

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"{field_name} debe ser una URL HTTPS")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} no puede incluir credenciales")

    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"{field_name} contiene un puerto no válido")

    return normalized


def normalize_currency_code(value: str, field_name: str = "currency_code") -> str:
    normalized = value.strip().upper()

    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise ValueError(f"{field_name} debe ser un código ISO 4217")

    return normalized


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


def build_product_submission(
    *,
    account_id: str,
    data_source_id: str,
    offer_id: str,
    title: str,
    description: str,
    link: str,
    image_link: str,
    price: float,
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

    try:
        decimal_price = Decimal(str(price))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("El precio debe ser numérico") from exc

    if not decimal_price.is_finite() or decimal_price <= 0:
        raise ValueError("El precio debe ser mayor que cero")

    amount_micros = int(
        (decimal_price * Decimal("1000000")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

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
