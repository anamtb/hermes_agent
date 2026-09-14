import ipaddress
import os
import re
import socket
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from mcp.server import MCPServer

from product_validation import (
    build_product_submission,
    normalize_currency_code,
    normalize_public_availability,
    product_resource_id,
    require_confirmation,
)


mcp = MCPServer("google-merchant")

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
MERCHANT_API_BASE = "https://merchantapi.googleapis.com"


class MerchantApiError(RuntimeError):
    """Controlled, sanitized failure returned by the Merchant API client."""

    def __init__(
        self,
        *,
        category: str,
        message: str,
        status_code: int | None = None,
        google_status: str | None = None,
        google_message: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.google_status = google_status
        self.google_message = google_message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "merchant_api_error",
            "category": self.category,
            "status_code": self.status_code,
            "message": str(self),
        }

        if self.google_status:
            result["google_status"] = self.google_status

        if self.google_message:
            result["google_message"] = self.google_message

        if self.details:
            result["details"] = self.details

        return result


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


def _merchant_error_category(status_code: int) -> tuple[str, str]:
    if status_code == 400:
        return "invalid_request", "Google rechazó el payload del producto"
    if status_code == 401:
        return "oauth_authentication", "El token OAuth no es válido o ha caducado"
    if status_code == 403:
        return "permission_denied", "La cuenta OAuth no tiene permisos suficientes"
    if status_code == 404:
        return "not_found", "No existe la cuenta, fuente de datos o endpoint indicado"
    if status_code == 409:
        return "conflict", "Google detectó un conflicto al guardar el producto"
    if status_code == 429:
        return "rate_limited", "Google ha limitado temporalmente las solicitudes"
    if status_code >= 500:
        return (
            "temporary_google_error",
            "Google Merchant no está disponible temporalmente",
        )

    return "unexpected_http_status", "Google devolvió un estado HTTP inesperado"


def _sanitize_external_data(value: Any, key: str = "") -> Any:
    sensitive_keys = {
        "accesstoken",
        "authorization",
        "clientsecret",
        "idtoken",
        "refreshtoken",
        "apikey",
    }

    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())

    if normalized_key in sensitive_keys:
        return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(item_key): _sanitize_external_data(item_value, str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [_sanitize_external_data(item) for item in value]

    if isinstance(value, str):
        return _safe_exception_message(RuntimeError(value))

    return value


def _merchant_api_error(response: httpx.Response) -> MerchantApiError:
    category, message = _merchant_error_category(response.status_code)
    google_status = None
    google_message = None
    details = None

    try:
        response_data = response.json()
    except ValueError:
        response_text = response.text.strip()
        if response_text:
            google_message = _safe_exception_message(
                RuntimeError(response_text)
            )
    else:
        error_data = (
            response_data.get("error", response_data)
            if isinstance(response_data, dict)
            else response_data
        )

        if isinstance(error_data, dict):
            raw_status = error_data.get("status")
            raw_message = error_data.get("message")
            raw_details = error_data.get("details")

            if isinstance(raw_status, str):
                google_status = _safe_exception_message(
                    RuntimeError(raw_status)
                )

            if isinstance(raw_message, str):
                google_message = _safe_exception_message(
                    RuntimeError(raw_message)
                )

            if raw_details:
                details = _sanitize_external_data(raw_details)

    return MerchantApiError(
        category=category,
        message=message,
        status_code=response.status_code,
        google_status=google_status,
        google_message=google_message,
        details=details,
    )


def _merchant_post(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        token = _get_access_token()
    except Exception as exc:
        raise MerchantApiError(
            category="oauth_token",
            message="No se pudo obtener el token OAuth de Google",
            google_message=_safe_exception_message(exc),
        ) from exc

    url = f"{MERCHANT_API_BASE}{path}"

    try:
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
    except httpx.RequestError as exc:
        raise MerchantApiError(
            category="network_error",
            message="No se pudo conectar con Google Merchant API",
            google_message=_safe_exception_message(exc),
        ) from exc

    if not 200 <= response.status_code < 300:
        raise _merchant_api_error(response)

    try:
        return response.json()
    except ValueError as exc:
        if not response.content:
            return {}

        raise MerchantApiError(
            category="invalid_response",
            message="Google devolvió una respuesta de éxito no válida",
            status_code=response.status_code,
        ) from exc


def _configured_account_id() -> str:
    account_id = _required_secret(
        "GOOGLE_MERCHANT_ACCOUNT_ID"
    ).strip()

    if not account_id.isdigit():
        raise ValueError(
            "GOOGLE_MERCHANT_ACCOUNT_ID no es válido"
        )

    return account_id


def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("La URL debe ser HTTPS y tener un host válido")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("No se pudo resolver el host") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(
                "La URL apunta a una dirección de red no permitida"
            )


def _check_public_url(
    url: str,
    *,
    require_image: bool,
) -> dict[str, Any]:
    current_url = url

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=False,
            headers={"User-Agent": "Hermes-Commerce-Agent/1.0"},
        ) as client:
            for _ in range(5):
                _validate_public_https_url(current_url)

                with client.stream("GET", current_url) as response:
                    status_code = response.status_code
                    content_type = (
                        response.headers
                        .get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )

                    if status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")

                        if not location:
                            raise ValueError("Redirección sin destino")

                        current_url = urljoin(current_url, location)
                        continue

                    public = status_code == 200

                    if require_image:
                        public = public and content_type.startswith("image/")

                    return {
                        "url": url,
                        "final_url": current_url,
                        "status_code": status_code,
                        "content_type": content_type or None,
                        "public": public,
                        "error": None,
                    }

        raise ValueError("Demasiadas redirecciones")
    except (httpx.RequestError, ValueError) as exc:
        return {
            "url": url,
            "final_url": current_url,
            "status_code": None,
            "content_type": None,
            "public": False,
            "error": str(exc),
        }


def _preflight_result(
    *,
    errors: list[str],
    warnings: list[str],
    submission: dict[str, Any] | None = None,
    link_check: dict[str, Any] | None = None,
    image_check: dict[str, Any] | None = None,
    landing_observation: dict[str, Any] | None = None,
    diagnostic: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the stable, JSON-serializable preflight response."""

    result: dict[str, Any] = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "normalized": submission,
        # Backwards-compatible fields used by google_merchant_upsert_product.
        "ready": not errors,
        "blockers": errors,
        "submission": submission,
        "link_check": link_check,
        "image_check": image_check,
        "landing_observation": landing_observation,
        "published": False,
    }

    if diagnostic is not None:
        result["diagnostic"] = diagnostic

    return result


def _safe_exception_message(exc: Exception) -> str:
    message = str(exc) or "Sin mensaje de excepción"
    patterns = (
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+",
        r"(?i)((?:access|refresh|id)_token|client_secret|api_key)"
        r"(\s*[=:]\s*)[^\s,;}]+",
    )

    for pattern in patterns:
        message = re.sub(pattern, r"\1[REDACTED]", message)

    return message[:1000]


def _unexpected_preflight_result(
    exc: Exception,
    *,
    stage: str,
) -> dict[str, Any]:
    return _preflight_result(
        errors=[f"Error interno inesperado durante {stage}"],
        warnings=[],
        diagnostic={
            "stage": stage,
            "exception_type": type(exc).__name__,
            "message": _safe_exception_message(exc),
        },
    )


def _upsert_error_result(
    error: dict[str, Any],
    *,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable upsert failure without leaking an MCP exception."""

    return {
        "ok": False,
        "submitted": False,
        "error": error,
        "preflight": preflight,
        "product_input": None,
    }


def _product_preflight(
    *,
    data_source_id: str,
    offer_id: str,
    title: str,
    description: str,
    link: str,
    image_link: str,
    price_eur: float,
    currency_code: str,
    availability: str,
    condition: str,
    brand: str,
    mpn: str,
    content_language: str,
    feed_label: str,
    gtin: str | None,
    public_price: float | None,
    public_currency: str,
    public_availability: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    landing_observation = {
        "price": public_price,
        "currency": public_currency or None,
        "availability": public_availability or None,
    }

    try:
        account_id = _configured_account_id()
    except (RuntimeError, ValueError) as exc:
        errors.append(str(exc))
        return _preflight_result(
            errors=errors,
            warnings=warnings,
            landing_observation=landing_observation,
        )

    try:
        submission = build_product_submission(
            account_id=account_id,
            data_source_id=data_source_id,
            offer_id=offer_id,
            title=title,
            description=description,
            link=link,
            image_link=image_link,
            price=price_eur,
            currency_code=currency_code,
            availability=availability,
            condition=condition,
            brand=brand,
            mpn=mpn,
            content_language=content_language,
            feed_label=feed_label,
            gtin=gtin,
        )
    except ValueError as exc:
        errors.append(str(exc))
        return _preflight_result(
            errors=errors,
            warnings=warnings,
            landing_observation=landing_observation,
        )

    link_check = _check_public_url(link, require_image=False)
    image_check = _check_public_url(image_link, require_image=True)

    if not link_check["public"]:
        detail = link_check.get("error")
        errors.append(
            "La URL pública del producto no responde con HTTP 200"
            + (f": {detail}" if detail else "")
        )

    if not image_check["public"]:
        detail = image_check.get("error")
        errors.append(
            "La imagen no responde públicamente como contenido image/*"
            + (f": {detail}" if detail else "")
        )

    if public_price is None:
        errors.append("Falta el precio observado en la landing pública")
    else:
        try:
            submitted_decimal = Decimal(str(price_eur))
            observed_decimal = Decimal(str(public_price))

            if (
                not submitted_decimal.is_finite()
                or not observed_decimal.is_finite()
                or observed_decimal <= 0
            ):
                raise ValueError("El precio no es finito o positivo")

            submitted_price = submitted_decimal.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            observed_price = observed_decimal.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            if submitted_price != observed_price:
                errors.append(
                    "El precio enviado no coincide con la landing pública"
                )
        except (InvalidOperation, ValueError):
            errors.append("El precio público observado no es válido")

    if not public_currency.strip():
        errors.append("Falta la moneda observada en la landing pública")
    else:
        try:
            observed_currency = normalize_currency_code(
                public_currency,
                "public_currency",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            submitted_currency = submission[
                "payload"
            ]["productAttributes"]["price"]["currencyCode"]

            if submitted_currency != observed_currency:
                errors.append(
                    "La moneda enviada no coincide con la landing pública"
                )

    if not public_availability.strip():
        errors.append(
            "Falta la disponibilidad observada en la landing pública"
        )
    else:
        try:
            observed_availability = normalize_public_availability(
                public_availability
            )
        except ValueError as exc:
            errors.append(str(exc).replace("availability", "public_availability"))
        else:
            submitted_availability = submission[
                "payload"
            ]["productAttributes"]["availability"]

            if submitted_availability != observed_availability:
                errors.append(
                    "La disponibilidad enviada no coincide con la landing pública"
                )

    return _preflight_result(
        errors=errors,
        warnings=warnings,
        submission=submission,
        link_check=link_check,
        image_check=image_check,
        landing_observation=landing_observation,
    )


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
def google_merchant_preflight_product(
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
    gtin: str | None = None,
    currency_code: str = "",
    content_language: str = "",
    feed_label: str = "",
    condition: str = "",
    public_price: float | None = None,
    public_currency: str = "",
    public_availability: str = "",
) -> dict[str, Any]:
    """Valida un producto y sus URLs sin publicarlo en Merchant Center.

    ``price_eur`` conserva el nombre histórico del parámetro; la moneda real
    siempre viene indicada por ``currency_code`` y debe coincidir con la
    observada en la landing pública.
    """

    try:
        return _product_preflight(
            data_source_id=data_source_id,
            offer_id=offer_id,
            title=title,
            description=description,
            link=link,
            image_link=image_link,
            price_eur=price_eur,
            currency_code=currency_code,
            availability=availability,
            condition=condition,
            brand=brand,
            mpn=mpn,
            content_language=content_language,
            feed_label=feed_label,
            gtin=gtin,
            public_price=public_price,
            public_currency=public_currency,
            public_availability=public_availability,
        )
    except Exception as exc:
        return _unexpected_preflight_result(
            exc,
            stage="google_merchant_preflight_product",
        )


def _get_product_by_identity(
    offer_id: str,
    content_language: str,
    feed_label: str,
) -> dict[str, Any]:
    account_id = _configured_account_id()
    product_id = product_resource_id(
        content_language,
        feed_label,
        offer_id,
    )

    return _merchant_get(
        f"/products/v1/accounts/{account_id}/products/{product_id}"
    )


@mcp.tool()
def google_merchant_get_product(
    offer_id: str,
    content_language: str,
    feed_label: str,
) -> dict[str, Any]:
    """Obtiene el producto procesado y su estado actual.

    Usa la cuenta configurada localmente. Herramienta de solo lectura.
    """

    return _get_product_by_identity(
        offer_id,
        content_language,
        feed_label,
    )


@mcp.tool()
def google_merchant_get_product_issues(
    offer_id: str,
    content_language: str,
    feed_label: str,
) -> dict[str, Any]:
    """Devuelve destinos e incidencias del producto procesado.

    Herramienta de solo lectura. Puede tardar varios minutos en reflejar una
    inserción reciente porque Merchant procesa el producto de forma asíncrona.
    """

    product = _get_product_by_identity(
        offer_id,
        content_language,
        feed_label,
    )
    status = product.get("productStatus") or {}

    return {
        "name": product.get("name"),
        "offer_id": product.get("offerId") or offer_id,
        "content_language": (
            product.get("contentLanguage") or content_language
        ),
        "feed_label": product.get("feedLabel") or feed_label,
        "destination_statuses": status.get("destinationStatuses", []),
        "item_level_issues": status.get("itemLevelIssues", []),
        "creation_date": status.get("creationDate"),
        "last_update_date": status.get("lastUpdateDate"),
        "google_expiration_date": status.get("googleExpirationDate"),
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
    currency_code: str,
    availability: str,
    condition: str,
    brand: str,
    mpn: str,
    content_language: str,
    feed_label: str,
    public_price: float,
    public_currency: str,
    public_availability: str,
    confirmation: str,
    gtin: str | None = None,
) -> dict[str, Any]:
    """Crea o actualiza un producto tras preflight y aprobación explícita.

    Requiere confirmation="PUBLICAR_EN_GOOGLE_MERCHANT". La cuenta viene de
    configuración local; fuente, idioma, feed label y moneda deben descubrirse
    o proporcionarse como datos verificados, nunca inferirse del usuario final.
    """

    try:
        require_confirmation(
            confirmation,
            "PUBLICAR_EN_GOOGLE_MERCHANT",
        )
    except RuntimeError as exc:
        return _upsert_error_result(
            {
                "type": "confirmation_required",
                "category": "confirmation_required",
                "status_code": None,
                "message": _safe_exception_message(exc),
            }
        )

    try:
        preflight = _product_preflight(
            data_source_id=data_source_id,
            offer_id=offer_id,
            title=title,
            description=description,
            link=link,
            image_link=image_link,
            price_eur=price_eur,
            currency_code=currency_code,
            availability=availability,
            condition=condition,
            brand=brand,
            mpn=mpn,
            content_language=content_language,
            feed_label=feed_label,
            gtin=gtin,
            public_price=public_price,
            public_currency=public_currency,
            public_availability=public_availability,
        )
    except Exception as exc:
        return _upsert_error_result(
            {
                "type": "internal_error",
                "category": "preflight_exception",
                "status_code": None,
                "message": "Error interno inesperado durante el preflight",
                "diagnostic": {
                    "exception_type": type(exc).__name__,
                    "message": _safe_exception_message(exc),
                },
            }
        )

    if not preflight["ready"]:
        return _upsert_error_result(
            {
                "type": "preflight_failed",
                "category": "validation",
                "status_code": None,
                "message": "Publicación bloqueada por preflight",
                "details": preflight["blockers"],
            },
            preflight=preflight,
        )

    submission = preflight["submission"]
    account_id = submission["account_id"]

    try:
        result = _merchant_post(
            (
                f"/products/v1/accounts/"
                f"{account_id}/productInputs:insert"
            ),
            params={
                "dataSource": submission["data_source"],
            },
            json_data=submission["payload"],
        )
    except MerchantApiError as exc:
        return _upsert_error_result(
            exc.as_dict(),
            preflight=preflight,
        )
    except Exception as exc:
        return _upsert_error_result(
            {
                "type": "internal_error",
                "category": "unexpected_exception",
                "status_code": None,
                "message": "Error interno inesperado durante el upsert",
                "diagnostic": {
                    "exception_type": type(exc).__name__,
                    "message": _safe_exception_message(exc),
                },
            },
            preflight=preflight,
        )

    return {
        "ok": True,
        "submitted": True,
        "error": None,
        "account_id": account_id,
        "data_source": submission["data_source"],
        "offer_id": submission["offer_id"],
        "product_id": submission["product_id"],
        "preflight": preflight,
        "product_input": result,
    }


if __name__ == "__main__":
    mcp.run()
