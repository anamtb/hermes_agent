"""Safe PcComponentes/Mirakl scaffold: capabilities only, no HTTP calls."""

import os
from typing import Any

from mcp.server import MCPServer


mcp = MCPServer("pccomponentes-commerce-scaffold")

REQUIRED_CONFIGURATION = (
    "PCCOMPONENTES_MIRAKL_API_URL",
    "PCCOMPONENTES_MIRAKL_API_KEY",
    "PCCOMPONENTES_SHOP_ID",
)


@mcp.tool()
def pccomponentes_get_capabilities() -> dict[str, Any]:
    """Describe scaffold state without authenticating or contacting Mirakl."""

    missing = [name for name in REQUIRED_CONFIGURATION if not os.environ.get(name)]
    return {
        "channel": "pccomponentes",
        "platform": "mirakl",
        "implementation_status": "SCAFFOLDED",
        "configured": not missing,
        "missing_configuration": missing,
        "network_request_performed": False,
        "capabilities": {
            "supports_catalog_lookup": False,
            "supports_catalog_publish": False,
            "supports_offer_publish": False,
            "supports_price_update": False,
            "supports_stock_update": False,
            "supports_orders": False,
            "supports_shipping_policy": False,
        },
        "planned": [
            "catalog and product mapping",
            "offer preflight and publication",
            "price and stock updates",
            "order reads",
        ],
    }


if __name__ == "__main__":
    mcp.run()
