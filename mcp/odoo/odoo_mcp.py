import base64
import html
import ipaddress
import json
import re
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from mcp.server import MCPServer


mcp = MCPServer("Odoo Commerce")


# El .env del perfil instalado estará dos niveles por encima de este archivo:
# .../commerce-test/.env
PROFILE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = PROFILE_DIR / ".env"


def _env_value(name: str) -> str:
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        if key.strip() == name:
            return value.strip().strip('"').strip("'")

    raise RuntimeError(f"Falta {name} en .env")


def _extract_product_jsonld(page_html: str) -> dict[str, Any] | None:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)</script>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def find_product(obj: Any) -> dict[str, Any] | None:
        if isinstance(obj, dict):
            object_type = obj.get("@type")

            if object_type == "Product":
                return obj

            if isinstance(object_type, list) and "Product" in object_type:
                return obj

            graph = obj.get("@graph")

            if isinstance(graph, list):
                for item in graph:
                    found = find_product(item)
                    if found:
                        return found

        elif isinstance(obj, list):
            for item in obj:
                found = find_product(item)
                if found:
                    return found

        return None

    for raw in scripts:
        try:
            decoded = html.unescape(raw).strip()
            data = json.loads(decoded)
        except Exception:
            continue

        found = find_product(data)

        if found:
            return found

    return None


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


@mcp.tool()
def odoo_set_stock(
    product_id: int,
    quantity: float,
) -> dict[str, Any]:
    """
    Establece la cantidad física disponible de un producto en Odoo.

    product_id es el ID de product.template.
    La cantidad se aplica a la variante principal del producto
    y al almacén principal de la compañía activa en Odoo.

    Restricciones:
- solo productos inventariables
- cantidad entre 0 y 1000 unidades
- no publica ni elimina productos
    """

    if quantity < 0:
        raise ValueError("El stock no puede ser negativo")

    if quantity > 1000:
        raise ValueError("El stock máximo permitido por esta herramienta es 1000")

    products = odoo_post(
        "product.template",
        "search_read",
        {
            "domain": [["id", "=", product_id]],
            "fields": [
                "name",
                "product_variant_id",
                "is_storable",
                "qty_available",
            ],
            "limit": 1,
        },
    )

    if not products:
        raise ValueError(f"No existe el producto con ID {product_id}")

    product = products[0]

    if not product.get("is_storable"):
        raise RuntimeError(
            "El producto no tiene activado el seguimiento de inventario"
        )

    variant = product.get("product_variant_id")

    if not variant:
        raise RuntimeError("El producto no tiene una variante asociada")

    variant_id = variant[0]

    warehouses = odoo_post(
        "stock.warehouse",
        "search_read",
        {
            "domain": [],
            "fields": ["name", "code", "lot_stock_id"],
            "limit": 2,
        },
    )

    if len(warehouses) != 1:
        raise RuntimeError(
            "Se esperaba exactamente un almacén visible para el bot"
        )

    warehouse = warehouses[0]

    result = odoo_post(
        "product.product",
        "write",
        {
            "ids": [variant_id],
            "vals": {
                "qty_available": float(quantity),
            },
        },
    )

    if result is not True:
        raise RuntimeError("Odoo no confirmó la actualización del stock")

    updated = odoo_post(
        "product.product",
        "search_read",
        {
            "domain": [["id", "=", variant_id]],
            "fields": [
                "name",
                "default_code",
                "qty_available",
                "free_qty",
                "virtual_available",
            ],
            "limit": 1,
        },
    )

    if not updated:
        raise RuntimeError("No se pudo verificar el stock actualizado")

    return {
        "updated": True,
        "warehouse": {
            "id": warehouse["id"],
            "name": warehouse["name"],
            "code": warehouse["code"],
            "stock_location": warehouse["lot_stock_id"],
        },
        "product": updated[0],
    }


@mcp.tool()
def odoo_publish_product(product_id: int) -> dict[str, Any]:
    """
    Publica un producto en el eCommerce de Odoo.

    Requiere que ODOO_ALLOW_PUBLISH=true esté configurado
    explícitamente en el .env del perfil.
    """

    values: dict[str, str] = {}

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    if values.get("ODOO_ALLOW_PUBLISH", "").lower() != "true":
        raise RuntimeError(
            "Publicación bloqueada. "
            "ODOO_ALLOW_PUBLISH no está autorizado."
        )

    product = odoo_get_product(product_id)

    if product.get("is_published"):
        return {
            "published": True,
            "already_published": True,
            "product": product,
        }

    result = odoo_post(
        "product.template",
        "write",
        {
            "ids": [product_id],
            "vals": {
                "is_published": True,
            },
        },
    )

    if result is not True:
        raise RuntimeError("Odoo no confirmó la publicación")

    updated = odoo_get_product(product_id)

    if not updated.get("is_published"):
        raise RuntimeError(
            "Odoo no confirmó que el producto esté publicado"
        )

    return {
        "published": True,
        "already_published": False,
        "product": updated,
    }


PRODUCT_IMAGE_DIR = Path(
    "/home/hermes/.hermes/assets/commerce-test/product-images"
)

MAX_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _get_product_for_image(product_id: int) -> dict[str, Any]:
    products = odoo_post(
        "product.template",
        "search_read",
        {
            "domain": [["id", "=", product_id]],
            "fields": [
                "name",
                "default_code",
                "is_published",
                "website_url",
            ],
            "limit": 1,
        },
    )

    if not products:
        raise ValueError(f"No existe el producto con ID {product_id}")

    return products[0]


def _write_product_image(
    product_id: int,
    image_bytes: bytes,
) -> dict[str, Any]:
    if not image_bytes:
        raise ValueError("La imagen está vacía")

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError("La imagen supera el límite de 10 MB")

    encoded = base64.b64encode(image_bytes).decode("ascii")

    result = odoo_post(
        "product.template",
        "write",
        {
            "ids": [product_id],
            "vals": {
                "image_1920": encoded,
            },
        },
    )

    if result is not True:
        raise RuntimeError(
            "Odoo no confirmó la actualización de la imagen"
        )

    updated = _get_product_for_image(product_id)

    return updated


def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("Solo se permiten URLs HTTPS")

    if not parsed.hostname:
        raise ValueError("La URL no contiene un host válido")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(
            "No se pudo resolver el host de la imagen"
        ) from exc

    for address in addresses:
        ip_text = address[4][0]
        ip = ipaddress.ip_address(ip_text)

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


def _download_public_image(url: str) -> tuple[bytes, str, str]:
    current_url = url

    with httpx.Client(
        timeout=20.0,
        follow_redirects=False,
        headers={
            "User-Agent": "Hermes-Commerce-Agent/1.0",
        },
    ) as client:

        for _ in range(5):
            _validate_public_https_url(current_url)

            response = client.get(current_url)

            if response.status_code in {
                301,
                302,
                303,
                307,
                308,
            }:
                location = response.headers.get("location")

                if not location:
                    raise RuntimeError(
                        "Redirección sin destino"
                    )

                current_url = urljoin(
                    current_url,
                    location,
                )
                continue

            response.raise_for_status()

            content_type = (
                response.headers
                .get("content-type", "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )

            if content_type not in ALLOWED_IMAGE_TYPES:
                raise ValueError(
                    f"Tipo de contenido no permitido: "
                    f"{content_type or 'desconocido'}"
                )

            image_bytes = response.content

            if len(image_bytes) > MAX_IMAGE_SIZE:
                raise ValueError(
                    "La imagen supera el límite de 10 MB"
                )

            return (
                image_bytes,
                content_type,
                current_url,
            )

    raise RuntimeError(
        "Demasiadas redirecciones al descargar la imagen"
    )


@mcp.tool()
def odoo_set_product_image_from_file(
    product_id: int,
    image_filename: str,
    confirmation: str = "",
) -> dict[str, Any]:
    """
    Establece la imagen principal de un producto usando un archivo
    proporcionado por el usuario.

    Solo permite archivos dentro de:
    /home/hermes/.hermes/assets/commerce-test/product-images/

    Si el producto está publicado requiere:
    confirmation="ACTUALIZAR_IMAGEN_PUBLICA"
    """

    product = _get_product_for_image(product_id)

    if (
        product.get("is_published")
        and confirmation != "ACTUALIZAR_IMAGEN_PUBLICA"
    ):
        raise RuntimeError(
            "El producto está publicado. "
            "Se requiere confirmación explícita."
        )

    root = PRODUCT_IMAGE_DIR.resolve()
    image_path = (root / image_filename).resolve()

    if not image_path.is_relative_to(root):
        raise ValueError(
            "La ruta de imagen no está permitida"
        )

    if not image_path.is_file():
        raise FileNotFoundError(
            f"No existe la imagen: {image_filename}"
        )

    if image_path.suffix.lower() not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        raise ValueError(
            "Solo se permiten JPG, JPEG, PNG y WEBP"
        )

    size = image_path.stat().st_size

    if size > MAX_IMAGE_SIZE:
        raise ValueError(
            "La imagen supera el límite de 10 MB"
        )

    image_bytes = image_path.read_bytes()

    updated = _write_product_image(
        product_id,
        image_bytes,
    )

    return {
        "updated": True,
        "source": "user_file",
        "image_filename": image_filename,
        "image_size_bytes": size,
        "product": updated,
    }


@mcp.tool()
def odoo_set_product_image_from_url(
    product_id: int,
    image_url: str,
    confirmation: str = "",
) -> dict[str, Any]:
    """
    Establece la imagen principal de un producto desde una URL
    pública HTTPS previamente seleccionada y aprobada por el usuario.

    Esta herramienta NO busca imágenes.

    Hermes debe:
    1. preguntar al usuario si quiere aportar una imagen o buscarla;
    2. si elige Internet, buscar el producto exacto;
    3. priorizar fabricante/proveedor autorizado;
    4. mostrar la fuente al usuario;
    5. obtener aprobación explícita;
    6. solo entonces llamar esta herramienta.

    Requiere siempre:
    confirmation="USAR_IMAGEN_WEB_APROBADA"
    """

    if confirmation != "USAR_IMAGEN_WEB_APROBADA":
        raise RuntimeError(
            "La imagen web no ha sido aprobada explícitamente"
        )

    product = _get_product_for_image(product_id)

    image_bytes, content_type, final_url = (
        _download_public_image(image_url)
    )

    updated = _write_product_image(
        product_id,
        image_bytes,
    )

    return {
        "updated": True,
        "source": "approved_web_url",
        "source_url": final_url,
        "content_type": content_type,
        "image_size_bytes": len(image_bytes),
        "product": updated,
    }


@mcp.tool()
def odoo_get_commerce_product(
    product_id: int,
) -> dict[str, Any]:
    """
    Obtiene los datos comerciales necesarios para publicar un producto
    en marketplaces.

    Incluye:
    - ficha Odoo
    - stock real
    - URL pública
    - URL pública de imagen
    - precio/moneda/disponibilidad observados en la página pública
      mediante JSON-LD cuando estén disponibles

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
                "description_sale",
                "list_price",
                "website_url",
                "is_published",
                "product_variant_id",
                "image_1920",
            ],
            "limit": 1,
        },
    )

    if not products:
        raise ValueError(
            f"No existe el producto con ID {product_id}"
        )

    product = products[0]

    variant = product.get("product_variant_id")

    if not variant:
        raise RuntimeError(
            "El producto no tiene variante asociada"
        )

    variant_id = variant[0]

    variants = odoo_post(
        "product.product",
        "search_read",
        {
            "domain": [["id", "=", variant_id]],
            "fields": [
                "name",
                "default_code",
                "qty_available",
                "free_qty",
                "virtual_available",
                "is_storable",
            ],
            "limit": 1,
        },
    )

    if not variants:
        raise RuntimeError(
            "No se pudo leer la variante del producto"
        )

    variant_data = variants[0]

    base_url = _env_value("ODOO_BASE_URL").rstrip("/")

    relative_url = product.get("website_url") or ""

    public_url = (
        urljoin(base_url + "/", relative_url.lstrip("/"))
        if relative_url
        else None
    )

    image_url = (
        f"{base_url}/web/image/"
        f"product.template/{product_id}/image_1920"
    )

    has_image = bool(product.get("image_1920"))

    public_page = {
        "status_code": None,
        "final_url": None,
        "jsonld_product_found": False,
        "price": None,
        "currency": None,
        "availability": None,
        "image": None,
    }

    image_check = {
        "status_code": None,
        "content_type": None,
        "public": False,
    }

    with httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Hermes-Commerce-Agent/1.0",
        },
    ) as client:

        if public_url and product.get("is_published"):
            response = client.get(public_url)

            public_page["status_code"] = response.status_code
            public_page["final_url"] = str(response.url)

            if response.status_code == 200:
                structured = _extract_product_jsonld(
                    response.text
                )

                if structured:
                    public_page[
                        "jsonld_product_found"
                    ] = True

                    offers = structured.get("offers")

                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}

                    if isinstance(offers, dict):
                        public_page["price"] = offers.get(
                            "price"
                        )
                        public_page["currency"] = offers.get(
                            "priceCurrency"
                        )
                        public_page[
                            "availability"
                        ] = offers.get("availability")

                    image = structured.get("image")

                    if isinstance(image, list):
                        image = image[0] if image else None

                    if isinstance(image, dict):
                        image = (
                            image.get("url")
                            or image.get("contentUrl")
                        )

                    public_page["image"] = image

        if has_image:
            image_response = client.get(image_url)

            image_check["status_code"] = (
                image_response.status_code
            )

            image_check["content_type"] = (
                image_response.headers
                .get("content-type", "")
                .split(";", 1)[0]
            )

            image_check["public"] = (
                image_response.status_code == 200
                and image_check["content_type"].startswith(
                    "image/"
                )
            )

    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "name": product.get("name"),
        "default_code": product.get("default_code"),
        "description_sale": product.get(
            "description_sale"
        ),
        "list_price": product.get("list_price"),
        "is_published": product.get("is_published"),
        "stock": {
            "qty_available": variant_data.get(
                "qty_available"
            ),
            "free_qty": variant_data.get("free_qty"),
            "virtual_available": variant_data.get(
                "virtual_available"
            ),
            "is_storable": variant_data.get(
                "is_storable"
            ),
        },
        "public_url": public_url,
        "image_url": image_url,
        "has_image": has_image,
        "image_check": image_check,
        "public_page": public_page,
    }


if __name__ == "__main__":
    mcp.run()
