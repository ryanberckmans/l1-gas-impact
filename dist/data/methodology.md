# L1 Gas Impact: measurement and coverage

Snapshot **2026-03-28–2026-09-27 UTC**, 184 complete days. Ethereum mainnet, chain 1. Snapshot `f983c100323ee081`. This is a fixed snapshot, not a live index.

## What the numbers mean

Actual transaction receipt `gasUsed`, including intrinsic gas and the L1 execution portion of blob transactions. Blob gas, gas limits, prices, fees and native execution on any other chain are excluded. Failed product transactions are included only where attribution is established. The plain ETH benchmark requires success, positive ETH value, empty input and exactly 21,000 gas.

All 70 product figures are lower bounds for selected populations. They are not complete footprints, a ranking of all Ethereum activity, or estimates of omitted gas. Ethereum-side activity for Solana, Hyperliquid, BSC and other chains is measured in the same Ethereum gas unit as every other row.

Count a full parent receipt only when its operation is exclusively attributable to the selected product. Do not allocate shared proofs, shared bridge settlements, unknown callbacks or mixed routes by association. Each included receipt hash occurs in only one product population. Native token costs on different chains are not comparable to this metric and are not added.

## Coverage by product

**Uniswap on L1.** Selected Ethereum routers, liquidity entrypoints and approvals; not Uniswap on other chains. Unknown, bridge and utility-only commands in the latest Universal Router are excluded.

**Lighter (primary instance).** Primary instance only, excluding Lighter on Robinhood and unresolved wrappers. Parent-transaction coverage is not gas coverage.

**Aave on L1.** Direct reviewed V2 and V3 pool methods; flash loans, V4 and wider callback-bearing or aggregator routes excluded.

**Compound on L1.** Direct reviewed Comet USDC, WETH and USDT market methods; other deployments and routers excluded.

**Morpho on L1.** Direct Morpho Blue methods, with empty callback data where applicable; vault wrappers and nonempty callbacks excluded.

**Curve on L1.** Selected Ethereum non-lending ERC20 legacy pools from the official registry. Factory-wide pools, routers, underlying lending routes and native-ETH callbacks excluded.

**Lido on L1.** Selected stETH/wstETH, withdrawal-request and oracle contracts. Token transfers included; unverified native-ETH withdrawal claims and wider staking modules excluded.

**ether.fi on L1.** Selected LiquidityPool, eETH/weETH, withdrawal and oracle contracts. Only reviewed methods and token transfers included; wider deployments and callbacks excluded.

**Ethena on L1.** Selected Ethereum USDe/sUSDe and ENA/sENA token and staking contracts, with reviewed methods. Aggregator routes and arbitrary callbacks excluded.

**Sky / Maker on L1.** Selected Maker/Sky DAI/USDS/SKY, savings and migration contracts. Wider vault, auction and governance deployments excluded.

**Aztec Network.** Current v5 and previous v4 rollup contracts and selected operator, governance and deposit methods. Earlier Ignition deployments, legacy zk.money, arbitrary execution and unresolved routes excluded.

**Starknet.** Direct state updates and selected bridges; shared SHARP proof transactions excluded without proportional allocation.

**ZKsync Era.** Identified direct-chain settlement and bridges; shared Gateway proofs and settlement excluded.

**Hyperliquid.** Ethereum-side CCTP, Across, Wormhole and DLN routes for Hyperliquid/HyperEVM. Native Hyperliquid execution and its Arbitrum bridge excluded; no allocation of Arbitrum settlement.

**Polygon PoS.** Polygon PoS checkpoints, reviewed staking and deposits, plus decoded bridges. Sidechain grouped with other non-L2 chains; unverified exits and arbitrary state messages excluded.

**EDGE Chain.** Ethereum-side bridge activity only. EDGE is an L3 settling via Arbitrum, excluded from both synthetic group subtotals.

**Other Chains.** Selected dedicated contracts, sender-specific inboxes and/or decoded chain-specific shared bridges, as listed per source. A chain with only bridge coverage is not assigned hypothetical settlement gas.

**Shared Bridges.** CCTP, Across, Wormhole and DLN: require a known source/destination chain and reviewed method. Incoming authenticated token-only routes included; mixed settlements, shared fills and arbitrary L1 callbacks excluded.

Lighter's included core receipts cover **11,818 of 90,480** observed deposit parent transactions and **33,150 of 34,382** withdrawal-claim parents. These are transaction coverage counts, not gas coverage; unresolved deposit wrappers remain a material gap.

## Verification and lineage

The prior release's validated observations for this same interval are preserved, except that its CCTP/Across cohorts are replaced by complete, decoded account histories. Replacement populations are compared against the removed totals and deduplicated; they are never added twice. Some prior Base and Arbitrum bridge figures decrease slightly because full decoding excludes deprecated or unreviewed methods and incoming messages addressed to unreviewed L1 contracts. Each decrease is reconciled to identified receipts; no omitted gas is estimated.

The expansion acquires **224 account populations**, covering **4,071,054 source transactions**, and reconciles each population's daily gas and count between Routescan histories and Blockchair aggregates. Overlapping pagination is deduplicated by hash. Conflicting index entries are checked against canonical Ethereum receipts and block membership. Documented April 16 duplicate-index repairs apply only to affected ETH4 responses; clean ETH3 responses remain unchanged. Incorrectly attributed contract creations, noncanonical entries and missing receipts are resolved using canonical receipts, transaction data and block membership. The exact corrections, accepted methods and exclusions are recorded in the evidence. Attribution-bearing ABI fields are decoded; opaque proof arrays in successful, reviewed settlement calls are not interpreted when the dedicated recipient or decoded chain identifier establishes exclusive attribution.

Original baseline aggregate-only populations retain their sampled verification, while original core and supplemental cohorts retain their full reconciliation records. The evidence distinguishes these scopes. This is not a full independent recount of Ethereum. A missing query or failed reconciliation blocks acceptance; completed queries with no matching activity can legitimately yield zero. Excluded or undiscovered activity is not represented as a measured zero.

## Interface and exports

The primary table is sorted by selected-period **million Ethereum gas per day**, descending, for every duration. “All L2 rollups”, “All L2 non-rollups” and “All alt L1s” sum only their classified, covered members and exist in this table's view layer, never as data records. The dated classification is detailed below. Polygon PoS is grouped with the non-L2 chains. EDGE is an L3 and belongs to none of the three subtotals. Group totals overlap their members; the ETH benchmark may overlap incidental product-related ETH transfers. Do not sum all rows.

Daily history bars show observed gas. The line is a trailing seven-day arithmetic mean with seven complete observations, including history before a zoomed window. Date controls, drag zoom, hover/touch inspection and keyboard controls operate on the daily chart. A custom chart window does not change the separately labeled main comparison interval. Product, duration, date and chart window are addressable in the URL. The change metric always compares the latest 30 days with the preceding 30. ETH-transfer equivalents divide gas by 21,000; they do not compare usefulness.

CSV, JSON, all eight language views and social metadata derive from this accepted snapshot and its current scope. The bulk transaction receipt CSVs are preserved in a separate archive and are not hosted with the app or included in its source repository. receipt-index.json retains every file checksum, transaction count and exact population coverage; receipt-validation.json records the full reconciliation, bound to the accepted inputs and verifier. To repeat the receipt recount, obtain the separate archive and run the documented validation command. These ledgers include every newly included receipt and previously published core receipts. Original supplemental approvals outside those core exports remain documented in the structured dataset. No synthetic aggregate receipt is created.

The public evidence ZIP includes dated prior-release provenance and current aggregate responses and checks. Historical files describe their own snapshots; they are not current totals. Full raw page corpora are preserved separately. Application source, private notes and conversation text are not part of the public deliverable.

## L2 aggregate classification

“All L2 rollups” and “All L2 non-rollups” are fixed cohorts by data-availability design at the end of this snapshot (2026-09-27). Rollups publish the data needed to reconstruct state to Ethereum. Non-rollups use external data availability. This distinction is not a security-stage or decentralization rating. [The classification file](/data/l2-classification.json) lists every covered L2, sources and migration notes.

Historical gas stays with the end-of-snapshot cohort, even before a migration. Mantle changed to Ethereum-only data availability on April 16 and Arbitrum Nova disabled DAC mode on August 31. These totals therefore compare the tracked footprints of fixed cohorts, not gas consumed exclusively under each historical architecture. Codex has unverified data availability and is excluded from both L2 sums; its individual observations remain available. It has no included gas in the latest 7- or 30-day window.

“All alt L1s” retains covered non-L2 chains, including Polygon PoS. EDGE is an L3 and is excluded from all three subtotals. Subtotals overlap their members and never become observations or receipts. The original evidence archive remains dated acquisition evidence; this classification annex is the current presentation taxonomy. Ratios of observed lower bounds are not themselves lower bounds. Execution-gas comparisons exclude blob gas and do not directly measure network effects or establish causation.
