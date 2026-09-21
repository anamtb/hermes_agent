---
name: commerce-product-launch
description: Orchestrate a product from verified identity and market research through pricing approval, Odoo publication, and approved downstream channel launches.
---

# Commerce Product Launch

## Purpose

Guide a product through a controlled ecommerce launch using:

- `market-intelligence` and web search for evidence-backed research;
- `commerce_calculate_pricing` for reusable price scenarios;
- Odoo MCP as the operational catalog and stock source of truth;
- the `channel-management` skill for downstream channel orchestration.

This skill orchestrates tools. It does not implement HTTP calls or low-level API
logic. Google Merchant is implemented. Amazon and PcComponentes/Mirakl are
scaffolded only: discover their declared capabilities, but do not imply that
catalog lookup, preflight, publication, price, stock, or orders work.

## Evidence labels

Label every material value as one of:

- `verified`: supported by a named source or tool result;
- `user_supplied`: supplied directly by the user and not independently verified;
- `estimate`: calculated or inferred, with method and assumptions;
- `unknown`: unavailable and not safe to infer.

Never invent GTIN, SKU/MPN, supplier, purchase cost, stock, tax rate,
specifications, competitor price, shipping/fees, availability, warranty, or
image rights.

## Product dossier

Use `knowledge/products/` for reusable evidence dossiers, one file per stable
product identity. Preserve existing dossiers. Create or update a dossier only
after the exact manufacturer/model/variant is established; use a stable slug
such as `manufacturer-model.yaml`.

The dossier stores verified identity/specifications, dated sources, market
observations, assumptions, and approvals. It must not duplicate live stock,
current public price, or publication status as if they were authoritative.
Odoo remains the operational source of truth for those values.

Prefer the stable SKU/MPN as the cross-channel identifier:

```text
Odoo default_code -> Merchant offerId -> future channel seller SKU
```

Do not use an internal Odoo ID when a stable SKU/MPN exists.

## State machine

Advance in order. Report the current state and unresolved blockers. Reading and
research do not require approval; the three gates below can never be inferred.

### DISCOVERY

Required to advance:

- user's commercial intent;
- candidate product or a clear request to identify it.

Ask only for missing business information. Do not ask for account IDs,
data-source IDs, company IDs, warehouse IDs, or other technical identifiers
that tools can discover.

### PRODUCT_IDENTITY

Required to advance:

- exact manufacturer;
- exact model/variant;
- MPN/SKU when one exists;
- GTIN only when verified (otherwise `unknown`);
- core specifications and their sources.

Do not mix visually similar, OEM, workstation, server, Max-Q, regional, or
capacity variants.

### SUPPLIER_AND_COST

Use `odoo_get_commerce_product` and `odoo_list_product_suppliers` when the
product exists. Required to price:

- purchase cost and currency;
- supplier status (`configured`, `user_supplied`, or `unknown`);
- available stock or explicitly unknown stock;
- shipping, other unit costs, and channel fees, or an explicit statement that
  each is unknown.

Never create a supplier silently. If no supplier is configured, ask the user
before any supplier association. Use `odoo_search_suppliers` to present existing
suppliers by human-readable name. Only after explicit approval may the workflow
call `odoo_set_product_supplier` with
`confirmation="ASOCIAR_PROVEEDOR_ODOO"`. That tool must never create a new
partner. If the supplier does not exist, stop and ask the user how to proceed.

Register a user-approved purchase cost only on an Odoo draft using
`odoo_set_product_cost` with `confirmation="REGISTRAR_COSTE_ODOO"`. Supplier
price and Odoo standard cost are separate facts; do not silently substitute one
for the other.

### MARKET_RESEARCH

Invoke the existing `market-intelligence` skill unless the user explicitly
chooses to skip market analysis. Search using manufacturer + model + MPN/SKU,
and GTIN when verified. Record source, observation date, country, currency,
tax inclusion, availability, shipping when known, and exact-variant confidence.

Do not present demand signals as proven sales. Do not reuse stale market prices
without clearly dating them.

### PRICING_PROPOSAL

Use `commerce_calculate_pricing`. Do not reproduce the calculation only in
natural language. Pass unknown optional costs as unknown, not zero; the tool
will mark the floor provisional.

Present:

- A — conservative / fast sale;
- B — moderate / balanced;
- C — aggressive / higher margin.

For each show net price, tax, customer gross price, purchase cost, known
logistics/other costs, known fees, total cost, unit profit, gross margin, and
market position. Show the price floor and all missing/estimated inputs.

Never recommend below the price floor unless the user explicitly authorizes a
loss/liquidation scenario. A provisional floor is not sufficient for unattended
publication.

### PRICE_APPROVAL — GATE 1

Stop and ask the user to choose or explicitly approve a price scenario. Record
the chosen gross/net price, tax rate, currency, assumptions, and timestamp.
Do not create/update the Odoo draft before this approval.

### ODOO_DRAFT

Use the existing Odoo draft tools. Create or update a draft only; preserve the
stable SKU in `default_code`. Set stock only from a verified Odoo value or a
specific user instruction. Never create a supplier silently.

### IMAGE_SELECTION

Ask the user to choose:

1. a user-provided image; or
2. an Internet image search.

For Internet images, match the exact variant, prefer manufacturer then
authorized distributor, show the original source and rights uncertainty, and
obtain approval before `odoo_set_product_image_from_url`. Never use a search
thumbnail or access private/localhost/link-local URLs. Never replace a
published image without explicit approval.

### ODOO_VALIDATION

Call `odoo_get_commerce_product`. Required before publication:

- stable SKU/MPN;
- real stock and availability;
- public URL;
- public image and successful image check;
- cost/supplier state;
- applicable tax data when available.

If data is unavailable, report `unknown/unavailable`; do not infer Odoo fields.

### ODOO_PUBLISH_APPROVAL — GATE 2

Show the exact draft, approved price, stock, public URL plan, and image. Stop
until the user explicitly approves publication in Odoo.

### ODOO_PUBLISHED

Only after Gate 2 call:

```text
odoo_publish_product(..., confirmation="PUBLICAR_EN_ODOO")
```

Then call `odoo_get_commerce_product` again. Require:

- landing HTTP 200;
- JSON-LD product found;
- public price and currency;
- public availability;
- publicly accessible image.

The landing price is the final source of truth for Merchant. If internal and
public price/currency/availability differ, stop and explain the mismatch.

### CHANNEL_DISCOVERY

Invoke `channel-management` after `ODOO_PUBLISHED` and ask:

> ¿En qué canales quieres comercializarlo?

Discover capabilities first and show only channels whose MCP is available,
with their truthful status (`IMPLEMENTED`, `SCAFFOLDED`, or `NOT_CONFIGURED`).
Typical choices are Google Merchant, Amazon, and PcComponentes. A scaffold may
be shown as planned/unavailable but cannot advance to publication.

For every selected implemented channel follow, independently:

```text
CHANNEL_PREFLIGHT
→ CHANNEL_PRICING
→ CHANNEL_APPROVAL
→ CHANNEL_PUBLISH
→ CHANNEL_REVIEW
→ CHANNEL_SYNC
```

Approval is per channel. Pricing and shipping assumptions from one channel do
not carry over to another. Unknown fees remain `UNKNOWN`, and the workflow must
not claim a definitive profit until all channel costs are known.

### MERCHANT_PREFLIGHT

This is Google Merchant's implementation of `CHANNEL_PREFLIGHT`.

Discover the configured account and API data source using Merchant read tools.
If several human-readable options exist, present their names. Do not ask the
user to type IDs that can be discovered.

Use Odoo `default_code`/verified MPN as `offerId`. Call
`google_merchant_preflight_product` with:

- offerId, title, description;
- final public product/image URLs;
- public landing price and currency;
- stock-derived and landing-confirmed availability;
- condition, brand, MPN;
- GTIN only if verified;
- content language and feed label from the target configuration/data source;
- selected data source.

Preflight must be `ready=true`. It performs no publication. Never substitute a
calculated price for a different observed landing price.

### MERCHANT_PUBLISH_APPROVAL — GATE 3

This is Google Merchant's `CHANNEL_APPROVAL` gate.

Show the complete normalized payload, data-source name, preflight evidence, and
all remaining uncertainties. Stop until the user explicitly approves Google
Merchant publication.

### MERCHANT_SUBMITTED

This is Google Merchant's `CHANNEL_PUBLISH` state.

Only after Gate 3 call:

```text
google_merchant_upsert_product(
  ...,
  confirmation="PUBLICAR_EN_GOOGLE_MERCHANT"
)
```

Never invent confirmation strings on behalf of the user.

### MERCHANT_REVIEW

This is Google Merchant's `CHANNEL_REVIEW` state.

Merchant processing is asynchronous. Use `google_merchant_get_product` and
`google_merchant_get_product_issues` after an appropriate delay. Report each
destination as approved, pending, disapproved, or not yet available; include
item-level issue descriptions and documentation links. Do not treat submission
success as approval.

## Completion summary

At the end report:

- product identity and master SKU;
- dossier path created/updated;
- approved pricing scenario and assumptions;
- Odoo draft/public state and validation evidence;
- Merchant submission identity and review status;
- unresolved issues, estimates, and the next safe action.
