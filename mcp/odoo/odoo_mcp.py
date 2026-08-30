from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer


mcp = MCPServer("Odoo Commerce")


# El .env del perfil instalado estará dos niveles por encima de este archivo:
# .../commerce-test/.env
PROFILE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = PROFILE_DIR / ".env"


def load_odoo_config() -> tuple[str, str]:
    values: dict[str, str] = {}

    if not ENV_FILE.exists():
        raise RuntimeError("No se encuentra el archivo .env del perfil")

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    base_url = values.get("ODOO_BASE_URL", "").rstrip("/")
    api_key = values.get("ODOO_API_KEY", "")

    if not base_url:
        raise RuntimeError("ODOO_BASE_URL no está configurado")

    if not api_key:
        raise RuntimeError("ODOO_API_KEY no está configurado")

    return base_url, api_key


def odoo_post(model: str, method: str, payload: dict[str, Any]) -> Any:
    base_url, api_key = load_odoo_config()

    url = f"{base_url}/json/2/{model}/{method}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "hermes-commerce-mcp/0.1",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
            message = detail.get("message", "Error de Odoo")
        except Exception:
            message = "Error HTTP devuelto por Odoo"

        raise RuntimeError(
            f"Odoo respondió HTTP {exc.response.status_code}: {message}"
        ) from None

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"No se pudo conectar con Odoo: {type(exc).__name__}"
        ) from None


@mcp.tool()
def odoo_list_products(
    limit: int = 20,
    search: str = "",
) -> list[dict[str, Any]]:
    """
    Lista productos de Odoo.

    Herramienta de solo lectura.
    Puede filtrar por nombre usando 'search'.
    """

    limit = max(1, min(limit, 100))

    domain = []

    if search.strip():
        domain = [["name", "ilike", search.strip()]]

    return odoo_post(
        "product.template",
        "search_read",
        {
            "domain": domain,
            "fields": [
                "name",
                "default_code",
                "list_price",
                "active",
                "sale_ok",
                "is_published",
                "website_url",
            ],
            "limit": limit,
        },
    )


@mcp.tool()
def odoo_create_draft_product(
    name: str,
    default_code: str = "",
    list_price: float = 0.0,
    description_sale: str = "",
) -> dict[str, Any]:
    """
    Crea un producto BORRADOR en Odoo.

    Restricciones:
- siempre fuerza is_published=False
- no permite publicar
- no elimina productos
- no modifica pagos
- no modifica contabilidad
    """

    name = name.strip()

    if not name:
        raise ValueError("El nombre del producto es obligatorio")

    if list_price < 0:
        raise ValueError("El precio no puede ser negativo")

    vals: dict[str, Any] = {
        "name": name,
        "list_price": float(list_price),
        "sale_ok": True,
        "active": True,
        "is_published": False,
    }

    if default_code.strip():
        vals["default_code"] = default_code.strip()

    if description_sale.strip():
        vals["description_sale"] = description_sale.strip()

    created_ids = odoo_post(
        "product.template",
        "create",
        {
            "vals_list": [vals],
        },
    )

    if not created_ids:
        raise RuntimeError("Odoo no devolvió el ID del producto creado")

    product_id = created_ids[0]

    products = odoo_post(
        "product.template",
        "search_read",
        {
            "domain": [["id", "=", product_id]],
            "fields": [
                "name",
                "default_code",
                "list_price",
                "active",
                "sale_ok",
                "is_published",
                "website_url",
            ],
            "limit": 1,
        },
    )

    if not products:
        raise RuntimeError(
            f"Producto {product_id} creado pero no pudo verificarse"
        )

    return {
        "created": True,
        "product": products[0],
    }


@mcp.tool()
def odoo_get_product(product_id: int) -> dict[str, Any]:
    """
    Obtiene un producto concreto de Odoo por ID.
    Herramienta de solo lectura.
    """

    products = odoo_post(
        "product.template",
        "search_read",
        {
            "domain": [["id", "=", product_id]],
            "fields": [
                "name",
                "default_code",
                "list_price",
                "description_sale",
                "active",
                "sale_ok",
                "is_published",
                "website_url",
            ],
            "limit": 1,
        },
    )

    if not products:
        raise ValueError(f"No existe el producto con ID {product_id}")

    return products[0]


@mcp.tool()
def odoo_update_draft_product(
    product_id: int,
    name: str = "",
    default_code: str = "",
    list_price: float | None = None,
    description_sale: str = "",
) -> dict[str, Any]:
    """
    Actualiza un producto de Odoo únicamente mientras NO esté publicado.

    Seguridad:
- no permite modificar productos publicados
- no puede publicar productos
- no elimina productos
- no modifica contabilidad ni pagos
    """

    current = odoo_get_product(product_id)

    if current.get("is_published"):
        raise RuntimeError(
            "El producto está publicado. "
            "odoo_update_draft_product solo puede modificar borradores."
        )

    vals: dict[str, Any] = {}

    if name.strip():
        vals["name"] = name.strip()

    if default_code.strip():
        vals["default_code"] = default_code.strip()

    if list_price is not None:
        if list_price < 0:
            raise ValueError("El precio no puede ser negativo")
        vals["list_price"] = float(list_price)

    if description_sale.strip():
        vals["description_sale"] = description_sale.strip()

    if not vals:
        raise ValueError("No se ha indicado ningún campo para actualizar")

    # La herramienta no acepta is_published como argumento.
    # Además volvemos a forzarlo a False.
    vals["is_published"] = False

    result = odoo_post(
        "product.template",
        "write",
        {
            "ids": [product_id],
            "vals": vals,
        },
    )

    if result is not True:
        raise RuntimeError("Odoo no confirmó la actualización del producto")

    updated = odoo_get_product(product_id)

    if updated.get("is_published"):
        raise RuntimeError(
            "Error de seguridad: el producto terminó publicado inesperadamente"
        )

    return {
        "updated": True,
        "product": updated,
    }


if __name__ == "__main__":
    mcp.run()
