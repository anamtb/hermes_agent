---
name: market-intelligence
description: Research and evaluate market opportunities for hardware products across ecommerce channels.
---

# Market Intelligence

## Purpose

Analyze a hardware product and determine where it has the strongest commercial opportunity.

This skill performs research and recommendations only.

It does not publish products, spend money, modify marketplace accounts or execute commercial transactions.

## Product Input

Product information is stored in:

knowledge/products/

Before starting an analysis:

1. Identify the requested product.
2. Read its YAML file.
3. Use the specifications, costs, target price and intended customer defined there.
4. Do not invent missing product information.
5. Clearly identify important missing information.

## Research Objective

Investigate whether the product has commercial potential and determine which sales channels appear most attractive.

Evaluate at least:

- Amazon
- eBay
- Google Shopping
- Own ecommerce website using Odoo

Other relevant channels may be included when useful.

## Research Process

### 1. Understand the Product

Identify:

- product name
- SKU
- category
- specifications
- target customer
- differentiating features
- cost
- target selling price
- available stock
- target geographic markets

### 2. Identify Potential Customers

Determine who is most likely to buy the product.

Possible segments may include:

- AI developers
- companies
- research organizations
- data centers
- engineering companies
- system integrators
- professional creators

Use the actual product characteristics to determine the relevant segments.

### 3. Research Competitors

Find products that solve a similar customer problem.

For each relevant competitor collect, when available:

- manufacturer
- product name
- platform
- price
- specifications
- positioning
- important differences

Prefer verifiable sources.

Do not invent competitor information.

### 4. Analyze Pricing

Determine:

- observed market price range
- representative competitor prices
- differences in specifications
- whether our target price appears competitive
- potential gross margin when cost information is available

Do not invent marketplace fees.

If platform fees are unknown, explicitly state that they require further investigation.

When this skill is invoked by `commerce-product-launch`, return normalized
market inputs rather than inventing a final price:

- `market_low`, `market_median`, and `market_high` as customer prices;
- currency, country, tax-inclusion status, availability, shipping when known;
- source URL and observation date for each price;
- exact-product confidence based on manufacturer, model, MPN/SKU, and verified
  GTIN when available.

Do not mix visually similar variants. The orchestration skill must pass these
inputs to `commerce_calculate_pricing`, which produces the conservative,
moderate, and aggressive scenarios and enforces the price floor.

### 5. Analyze Demand Signals

Look for observable signals that may indicate market interest.

Examples:

- number and variety of competing products
- marketplace presence
- pricing consistency
- product availability
- search interest
- reviews when available
- related product activity
- industry trends
- target customer activity

These are demand signals.

They are not proof of actual sales volume.

Never claim to know marketplace sales numbers unless they come from a verified source.

### 6. Evaluate Sales Channels

Evaluate:

- Amazon
- eBay
- Google Shopping
- Odoo ecommerce

For each channel analyze:

- audience fit
- competition
- pricing
- apparent demand signals
- operational complexity
- potential margin
- advantages
- disadvantages
- risks

## Opportunity Score

Give every channel an opportunity score from 0 to 100.

Use:

- Demand signals: 30 points
- Competition attractiveness: 20 points
- Price positioning: 15 points
- Potential margin: 15 points
- Audience fit: 10 points
- Operational feasibility: 10 points

Explain the reasoning behind the score.

The score is a decision-support estimate, not a factual measurement of marketplace demand.

## Output

Produce a structured market intelligence report containing:

### Product Summary

Briefly explain the product and its intended customer.

### Market Findings

Summarize the most relevant observed market information.

### Competitors

List the strongest comparable products discovered.

### Channel Analysis

For every channel provide:

- opportunity score
- advantages
- disadvantages
- pricing observations
- competitive situation
- risks
- recommended action

### Ranking

Rank channels from strongest to weakest opportunity.

Example:

1. Google Shopping + Odoo — 82/100
2. Amazon — 75/100
3. eBay — 61/100

### Recommendation

Choose one of:

- LAUNCH
- SMALL TEST
- INVESTIGATE FURTHER
- DO NOT LAUNCH

Explain why.

## Safety and Commercial Rules

Do not:

- purchase products
- create paid advertisements
- publish marketplace listings
- change prices
- create seller accounts
- accept contractual conditions
- spend company money
- make unsupported claims about demand

This skill performs research and recommendations only.

Any commercial action requiring money, publication, contractual acceptance or account modification requires a separate authorized skill or human approval.
