import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer


mcp = MCPServer("google-merchant")

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
MERCHANT_API_BASE = "https://merchantapi.googleapis.com"


def _load_env() -> dict[str, str]:
    values: dict[str, str] = {}

    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def _required_secret(name: str) -> str:
    values = _load_env()
    value = values.get(name) or os.environ.get(name)

    if not value:
        raise RuntimeError(
            f"Falta la configuración requerida: {name}"
        )

    return value


def _get_access_token() -> str:
    client_id = _required_secret("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = _required_secret("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = _required_secret("GOOGLE_OAUTH_REFRESH_TOKEN")

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Google OAuth error {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError(
            "Google no devolvió un access_token"
        )

    return access_token


def _merchant_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _get_access_token()

    url = f"{MERCHANT_API_BASE}{path}"

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Merchant API error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    return response.json()


def _merchant_post(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _get_access_token()

    url = f"{MERCHANT_API_BASE}{path}"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            params=params,
            json=json_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Merchant API error {response.status_code}: "
            f"{response.text[:1500]}"
        )

    return response.json()


@mcp.tool()
def google_merchant_list_accounts() -> dict[str, Any]:
    """
    Lista las cuentas de Google Merchant Center accesibles
    por el usuario OAuth.

    Herramienta de solo lectura.
    """

    result = _merchant_get(
        "/accounts/v1/accounts",
        {
            "pageSize": 100,
        },
    )

    accounts = result.get("accounts", [])

    return {
        "count": len(accounts),
        "accounts": accounts,
        "next_page_token": result.get("nextPageToken"),
    }


@mcp.tool()
def google_merchant_get_account(
    account_id: str,
) -> dict[str, Any]:
    """
    Obtiene una cuenta concreta de Google Merchant Center.

    Herramienta de solo lectura.
    """

    account_id = account_id.strip()

    if not account_id.isdigit():
        raise ValueError(
            "account_id debe ser el ID numérico de Merchant Center"
        )

    return _merchant_get(
        f"/accounts/v1/accounts/{account_id}"
    )


@mcp.tool()
def google_merchant_list_products(
    account_id: str,
) -> dict[str, Any]:
    """
    Lista productos procesados de Google Merchant Center.

    Incluye su estado final y posibles problemas del producto.

    Herramienta de solo lectura.
    """

    account_id = account_id.strip()

    if not account_id.isdigit():
        raise ValueError(
            "account_id debe ser el ID numérico de Merchant Center"
        )

    result = _merchant_get(
        f"/products/v1/accounts/{account_id}/products",
        {
            "pageSize": 100,
        },
    )

    products = result.get("products", [])

    return {
        "count": len(products),
        "products": products,
        "next_page_token": result.get("nextPageToken"),
    }


@mcp.tool()
def google_merchant_list_data_sources(
    account_id: str,
) -> dict[str, Any]:
    """
    Lista las fuentes de datos configuradas en Merchant Center.

    Herramienta de solo lectura.
    """

    account_id = account_id.strip()

    if not account_id.isdigit():
        raise ValueError(
            "account_id debe ser el ID numérico de Merchant Center"
        )

    result = _merchant_get(
        f"/datasources/v1/accounts/{account_id}/dataSources",
        {
            "pageSize": 100,
        },
    )

    sources = result.get("dataSources", [])

    return {
        "count": len(sources),
        "data_sources": sources,
        "next_page_token": result.get("nextPageToken"),
    }


@mcp.tool()
def google_merchant_upsert_product(
    data_source_id: str,
    offer_id: str,
    title: str,
    description: str,
    link: str,
    image_link: str,
    price_eur: float,
    availability: str,
    brand: str,
    mpn: str,
    confirmation: str = "",
    gtin: str | None = None,
) -> dict[str, Any]:
    """
    Crea o actualiza un producto en Google Merchant Center.

    Usa la cuenta configurada en GOOGLE_MERCHANT_ACCOUNT_ID.

    Requiere confirmación explícita:
    confirmation="PUBLICAR_EN_GOOGLE_MERCHANT"

    availability:
    IN_STOCK
    OUT_OF_STOCK
    PREORDER
    BACKORDER
    """

    if confirmation != "PUBLICAR_EN_GOOGLE_MERCHANT":
        raise RuntimeError(
            "Publicación bloqueada. "
            "Se requiere confirmación explícita."
        )

    account_id = _required_secret(
        "GOOGLE_MERCHANT_ACCOUNT_ID"
    ).strip()

    if not account_id.isdigit():
        raise ValueError(
            "GOOGLE_MERCHANT_ACCOUNT_ID no es válido"
        )

    data_source_id = data_source_id.strip()

    if not data_source_id.isdigit():
        raise ValueError(
            "data_source_id debe ser numérico"
        )

    offer_id = offer_id.strip()

    if not offer_id:
        raise ValueError("offer_id es obligatorio")

    if price_eur <= 0:
        raise ValueError(
            "El precio debe ser mayor que cero"
        )

    allowed_availability = {
        "IN_STOCK",
        "OUT_OF_STOCK",
        "PREORDER",
        "BACKORDER",
    }

    availability = availability.strip().upper()

    if availability not in allowed_availability:
        raise ValueError(
            "availability no es válido"
        )

    for field_name, url in {
        "link": link,
        "image_link": image_link,
    }.items():
        if not url.startswith("https://"):
            raise ValueError(
                f"{field_name} debe ser una URL HTTPS"
            )

    amount_micros = int(
        round(price_eur * 1_000_000)
    )

    attributes: dict[str, Any] = {
        "title": title.strip(),
        "description": description.strip(),
        "link": link.strip(),
        "imageLink": image_link.strip(),
        "availability": availability,
        "condition": "NEW",
        "brand": brand.strip(),
        "mpn": mpn.strip(),
        "price": {
            "amountMicros": str(amount_micros),
            "currencyCode": "EUR",
        },
    }

    if gtin:
        attributes["gtins"] = [gtin.strip()]

    data_source_name = (
        f"accounts/{account_id}/"
        f"dataSources/{data_source_id}"
    )

    payload = {
        "offerId": offer_id,
        "contentLanguage": "es",
        "feedLabel": "ES",
        "productAttributes": attributes,
    }

    result = _merchant_post(
        (
            f"/products/v1/accounts/"
            f"{account_id}/productInputs:insert"
        ),
        params={
            "dataSource": data_source_name,
        },
        json_data=payload,
    )

    return {
        "submitted": True,
        "account_id": account_id,
        "data_source": data_source_name,
        "offer_id": offer_id,
        "product_input": result,
    }


if __name__ == "__main__":
    mcp.run()
