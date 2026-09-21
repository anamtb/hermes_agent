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

## Non-negotiable rules

- Every channel has its own publication approval gate.
- Never publish without a successful preflight.
- Pricing may vary by channel and requires channel-specific evidence.
- Never invent fees, shipping, marketplace IDs, ASINs, or Mirakl IDs.
- Unknown costs remain `UNKNOWN`; do not turn them into zero silently.
- Odoo remains the operational source of truth.
- The SKU is the stable cross-channel seller identifier.
- Never store API keys or tokens in product dossiers.
