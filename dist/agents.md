# L1 Gas Impact: data guide

This public research snapshot compares Ethereum L1 execution gas directly attributable to selected L1 applications, Ethereum scaling systems, and other chains. It includes Uniswap on L1, Lighter's primary instance, major DeFi protocols, and Ethereum-side activity for chains including Solana, Hyperliquid, BNB Smart Chain and Polygon PoS. The complete roster is in [the query manifest](/data/query-manifest.json). Plain ETH transfers provide a contextual benchmark. The interval is 2026-03-28 00:00:00 UTC through, but not including, 2026-09-28 00:00:00 UTC.

## Measurement and scope

All values are observed Ethereum L1 receipt `gasUsed`, in integer gas units. Intrinsic gas and the execution portion of blob transactions are included. Blob gas, gas limits, gas prices, fees and native execution on other chains are excluded. Product populations include attributable failures. The ETH benchmark includes only successful positive-value transactions with empty calldata and exactly 21,000 gas used.

Every product figure is a lower bound for selected populations. Coverage differs by product; this is not a complete census or a ranking of all Ethereum activity. Dedicated contracts, reviewed methods, verified inbox senders and decoded chain-specific bridges establish attribution. Shared settlements, shared proofs, arbitrary callbacks, mixed routes and unreviewed methods are excluded. Missing queries cannot silently become zeros. A completed query with no matching transaction can yield zero within its stated scope.

Lighter means its primary deployment, excluding Lighter on Robinhood. Uniswap on L1 excludes Uniswap's execution on rollups; Unichain is a separate chain row. Hyperliquid's Arbitrum bridge does not create an allocation of Arbitrum settlement gas. Shared Starknet SHARP and ZKsync Gateway transactions are excluded. Polygon PoS is a sidechain, grouped with the other non-L2 chains. EDGE is an L3 and is excluded from all group subtotals. See the per-product coverage notes and [methodology](/data/methodology.md).

## Reading the interface

The primary table sorts million Ethereum gas per day descending for each selected interval. Mean gas per day is interval gas divided by its complete UTC days. The default period is 30 days; seven-day and six-month views are available.

“All L2 rollups”, “All L2 non-rollups” and “All alt L1s” are presentation-only sums of covered members. The fixed L2 cohorts use end-of-snapshot data availability, not historical day-by-day architecture: Ethereum data availability versus external data availability. Codex remains unclassified and is excluded from both L2 sums. See the [dated classification and per-chain sources](/data/l2-classification.json), including migration notes. “All alt L1s” includes Polygon PoS. These summaries never appear as exported observations. They overlap their members. Do not sum all table rows: the contextual ETH benchmark may also overlap incidental product-related transfers.

Daily chart bars show actual gas; the line shows a trailing seven-day arithmetic mean, including history before a zoomed window. Duration and custom date controls, pointer inspection, drag zoom and keyboard navigation are available. Custom chart windows do not change the separately labeled comparison interval. URL parameters preserve the selected day and chart window. The change metric always compares the latest 30 days with the preceding 30. ETH-transfer equivalents divide gas by 21,000; they do not compare transaction usefulness.

## Files

- [Daily CSV](/data/l1-gas-daily.csv): date, product, activity, gas and transaction count.
- [Detailed JSON](/data/dataset.json): metadata and per-source daily observations.
- [Display summary](/data/summary.json): daily product series, taxonomy and snapshot identity; no synthetic observations.
- [Query manifest](/data/query-manifest.json): source identities, predicates, verification, exclusions and checksummed receipt downloads.
- [Evidence archive](/data/l1-gas-evidence.zip): aggregate responses, verification records and clearly dated baseline provenance. Full bulky raw page corpora are preserved separately.

Receipt CSVs for the selected product are linked in the interface and all receipt parts are indexed in the manifest. Each export states its population coverage. All newly included receipts and previously published core receipts are exported; some original supplemental approval cohorts remain in the structured dataset rather than the core receipt downloads. Static HTML includes exact tables before JavaScript runs.

The interface is available in eight languages and follows the system theme by default, with persistent System, Light and Dark preferences. Social artwork and print use intentional fixed palettes. All public files are read-only. There is no authentication, write API, transaction signing or live chain acquisition in the website.
