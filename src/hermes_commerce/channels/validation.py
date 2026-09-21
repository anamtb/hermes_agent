"""Reusable normalization for channel adapters."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from hermes_commerce.domain.identifiers import validate_gtin
from hermes_commerce.domain.inventory import Availability
from hermes_commerce.domain.product import ProductCondition


AVAILABILITY_ALIASES = {
    "instock": Availability.IN_STOCK.value,
    "outofstock": Availability.OUT_OF_STOCK.value,
    "preorder": Availability.PREORDER.value,
    "backorder": Availability.BACKORDER.value,
}
CONDITION_ALIASES = {
    "new": ProductCondition.NEW.value,
    "newcondition": ProductCondition.NEW.value,
    "refurbished": ProductCondition.REFURBISHED.value,
    "refurbishedcondition": ProductCondition.REFURBISHED.value,
    "used": ProductCondition.USED.value,
    "usedcondition": ProductCondition.USED.value,
}


def _alias(value: str) -> str:
    leaf = value.strip().rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]", "", leaf.lower())


def normalize_availability(value: str) -> str:
    try:
        return AVAILABILITY_ALIASES[_alias(value)]
    except KeyError as exc:
        raise ValueError("availability no es válido") from exc


def normalize_condition(value: str) -> str:
    try:
        return CONDITION_ALIASES[_alias(value)]
    except KeyError as exc:
        raise ValueError("condition no es válido") from exc


def normalize_currency_code(value: str, field_name: str = "currency_code") -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise ValueError(f"{field_name} debe ser un código ISO 4217")
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


__all__ = [
    "normalize_availability",
    "normalize_condition",
    "normalize_currency_code",
    "validate_gtin",
    "validate_https_url",
]
