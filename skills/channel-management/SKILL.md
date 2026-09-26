---
name: channel-management
description: Orchestrate safe discovery, pricing, approval, publication, review, and synchronization for configured commerce channels.
---

# Channel Management

## Purpose

Coordinate downstream sales channels after Odoo has published and verified the
public product. Odoo remains the operational master. This skill never treats a
channel as a replacement source of truth.

The stable cross-channel identifier is the Odoo `default_code` / verified SKU.
Channel IDs (Google offer ID, Amazon ASIN, Mirakl IDs) are mappings and must not
be placed in the shared `CommerceProduct`.

## State machine

```text
CHANNEL_DISCOVERY
→ CHANNEL_PREFLIGHT
→ CHANNEL_PRICING
→ CHANNEL_APPROVAL
→ CHANNEL_PUBLISH
→ CHANNEL_REVIEW
→ CHANNEL_SYNC
```

### CHANNEL_DISCOVERY

Discover channel capabilities and configuration using read-only tools. Offer
only channels whose MCP can be discovered. Distinguish `IMPLEMENTED`,
`SCAFFOLDED`, and `NOT_CONFIGURED`. A scaffold is not publishable.

### CHANNEL_PREFLIGHT

Build and validate a channel-specific representation from the verified Odoo
public product. Do not publish. Never invent SKU, GTIN, marketplace identifier,
shipping, fees, policies, or required account configuration.

### CHANNEL_PRICING

Calculate each channel independently using `base_cost`, `shipping_cost`,
`channel_fixed_fee`, `channel_percent_fee`, and `other_channel_costs`. Unknown
fees remain `UNKNOWN`; do not report definitive profit or margin while a cost
is unknown. A price approved for one channel does not approve another.

### CHANNEL_APPROVAL — GATE

Show the destination, normalized payload, price, known and unknown costs,
shipping assumptions, identifiers, preflight status, and expected write. Stop
until the user explicitly approves publication for that specific channel.

### CHANNEL_PUBLISH

Publish only when the channel advertises the capability, preflight is ready,
and the specific channel approval is present. Never manufacture confirmation
tokens. Amazon and PcComponentes are currently scaffolds and must stop here.

### CHANNEL_REVIEW

Read status and issues. Submission is not approval. Report pending, approved,
rejected, unavailable, or unknown without hiding channel diagnostics.

### CHANNEL_SYNC

Reconcile channel views with Odoo. Odoo remains master for catalog, stock, and
operational data. Use supported updates only; otherwise report the missing
capability and required next action.

## Google Merchant shipping policy

Shipping configuration is a separate account-level write and has its own gate;
product publication approval never authorizes it.

```text
SHIPPING_DISCOVERY
→ SHIPPING_PREFLIGHT
→ SHIPPING_APPROVAL
→ SHIPPING_APPLY
→ SHIPPING_REVIEW
```

1. Read the current resource with `google_merchant_get_shipping_settings`.
2. Call `google_merchant_prepare_shipping_policy` with user-supplied country,
   service name, currency, rate, handling days, and transit days. Never invent
   any of these values. Review the returned full resource, diff, and `etag`.
3. Stop at `SHIPPING_APPROVAL`. Show whether the service is created or updated,
   the exact price, countries, timings, active state, preserved services and
   warehouses, and the expected `etag`.
4. Only after explicit approval call `google_merchant_set_shipping_policy` with
   `confirmation="CONFIGURAR_ENVIO_GOOGLE_MERCHANT"` and the approved `etag`.
5. If the `etag` changed, do not retry the write automatically. Repeat discovery
   and preflight, show the new diff, and obtain a new approval.
6. Read the shipping settings again and report the observed result.

The tool supports only `FREE` and `FLAT_RATE`. Other shipping models are not to
be approximated with a flat rate. Google replaces the complete shipping
resource on insert, so all unrelated services and warehouses must be preserved.

## Non-negotiable rules

- Every channel has its own publication approval gate.
- Shipping policy has a separate approval gate from product publication.
- Never publish without a successful preflight.
- Pricing may vary by channel and requires channel-specific evidence.
- Never invent fees, shipping, marketplace IDs, ASINs, or Mirakl IDs.
- Unknown costs remain `UNKNOWN`; do not turn them into zero silently.
- Odoo remains the operational source of truth.
- The SKU is the stable cross-channel seller identifier.
- Never store API keys or tokens in product dossiers.
