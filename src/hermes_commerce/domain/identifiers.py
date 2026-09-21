"""Channel-neutral product identifiers."""

from __future__ import annotations

from dataclasses import dataclass


GTIN_LENGTHS = {8, 12, 13, 14}


def validate_gtin(value: str) -> str:
    normalized = value.strip()
    if not normalized.isdigit() or len(normalized) not in GTIN_LENGTHS:
        raise ValueError("gtin debe tener 8, 12, 13 o 14 dígitos")

    body = normalized[:-1]
    weighted_sum = sum(
        int(digit) * (3 if (len(body) - index) % 2 else 1)
        for index, digit in enumerate(body)
    )
    expected = (10 - weighted_sum % 10) % 10
    if int(normalized[-1]) != expected:
        raise ValueError("gtin tiene un dígito de control no válido")
    return normalized


@dataclass(frozen=True)
class SKU:
    """Stable cross-channel seller identifier."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("sku es obligatorio")
        if any(character.isspace() for character in normalized):
            raise ValueError("sku no puede contener espacios")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class GTIN:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", validate_gtin(self.value))

    def __str__(self) -> str:
        return self.value
