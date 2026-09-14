"""Pure validation helpers for Google Merchant product submissions."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote


ALLOWED_AVAILABILITY = {
    "IN_STOCK",
    "OUT_OF_STOCK",
    "PREORDER",
    "BACKORDER",
}
ALLOWED_CONDITIONS = {"NEW", "REFURBISHED", "USED"}
GTIN_LENGTHS = {8, 12, 13, 14}
PUBLIC_AVAILABILITY = {
    "instock": "IN_STOCK",
    "outofstock": "OUT_OF_STOCK",
    "preorder": "PREORDER",
    "backorder": "BACKORDER",
}


def require_confirmation(value: str, expected: str) -> None:
    if value != expected:
        raise RuntimeError(
            "Publicación bloqueada. Se requiere confirmación explícita."
        )


def normalize_availability(value: str) -> str:
    normalized = value.strip().upper()

    if normalized not in ALLOWED_AVAILABILITY:
        raise ValueError("availability no es válido")

    return normalized


def normalize_public_availability(value: str) -> str:
    normalized = value.strip().rstrip("/").rsplit("/", 1)[-1].lower()

    if normalized in PUBLIC_AVAILABILITY:
        return PUBLIC_AVAILABILITY[normalized]

    return normalize_availability(value)


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
    currency_code = currency_code.strip().upper()
    content_language = content_language.strip()
    feed_label = feed_label.strip()
    condition = condition.strip().upper()

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

    for field_name, url in {
        "link": link.strip(),
        "image_link": image_link.strip(),
    }.items():
        if not url.startswith("https://"):
            raise ValueError(f"{field_name} debe ser una URL HTTPS")

    if not re.fullmatch(r"[A-Z]{3}", currency_code):
        raise ValueError("currency_code debe ser un código ISO 4217")

    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2})?", content_language):
        raise ValueError("content_language no es válido")

    if condition not in ALLOWED_CONDITIONS:
        raise ValueError("condition no es válido")

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
        "link": link.strip(),
        "imageLink": image_link.strip(),
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
        normalized_gtin = gtin.strip()

        if not normalized_gtin.isdigit() or len(normalized_gtin) not in GTIN_LENGTHS:
            raise ValueError("gtin debe tener 8, 12, 13 o 14 dígitos")

        attributes["gtins"] = [normalized_gtin]

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
