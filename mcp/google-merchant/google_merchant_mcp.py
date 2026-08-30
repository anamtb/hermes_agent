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


if __name__ == "__main__":
    mcp.run()
