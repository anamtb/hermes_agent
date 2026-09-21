"""Safe Amazon SP-API scaffold: capability discovery only, no HTTP calls."""

import os
from typing import Any

from mcp.server import MCPServer


mcp = MCPServer("amazon-commerce-scaffold")

REQUIRED_CONFIGURATION = (
    "AMAZON_SP_API_CLIENT_ID",
    "AMAZON_SP_API_CLIENT_SECRET",
    "AMAZON_SP_API_REFRESH_TOKEN",
    "AMAZON_SELLER_ID",
    "AMAZON_MARKETPLACE_ID",
)


@mcp.tool()
def amazon_get_capabilities() -> dict[str, Any]:
    """Describe scaffold state without authenticating or contacting Amazon."""

    missing = [name for name in REQUIRED_CONFIGURATION if not os.environ.get(name)]
    return {
        "channel": "amazon",
        "implementation_status": "SCAFFOLDED",
        "configured": not missing,
        "missing_configuration": missing,
        "network_request_performed": False,
        "capabilities": {
            "supports_account_discovery": False,
            "supports_catalog_lookup": False,
            "supports_catalog_publish": False,
            "supports_listing_preflight": False,
            "supports_price_update": False,
            "supports_stock_update": False,
            "supports_orders": False,
            "supports_shipping_policy": False,
        },
        "planned": [
            "account configuration validation",
            "catalog lookup",
            "listing preflight",
            "listing publication",
            "price and stock updates",
        ],
    }


if __name__ == "__main__":
    mcp.run()
