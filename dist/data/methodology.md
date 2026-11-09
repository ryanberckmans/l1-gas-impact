# L1 Gas Impact: measurement and coverage

Snapshot **2026-05-09–2026-11-08 UTC**, 184 complete days. Ethereum mainnet, chain 1. Snapshot `2945bd63e0ee6d53`. This is a fixed research snapshot.

## Measurement

Receipt and log data from [Routescan](https://routescan.io), canonical RPC evidence from Routescan and [PublicNode](https://ethereum.publicnode.com/), and independent aggregate data from [Blockchair](https://blockchair.com).

Actual Ethereum transaction receipt `gasUsed`, including intrinsic gas and the execution portion of blob transactions. Blob gas, gas limits, prices, fees and native execution on other chains are excluded. Failed product transactions count only when exclusive attribution is established. The ETH benchmark requires a successful positive-value transfer with empty input and exactly 21,000 gas.

These are lower bounds for selected directly attributable populations, not complete product footprints. A shared router or operator alone does not establish attribution. Unknown methods, mixed routes and unresolved callbacks remain excluded. Receipt hashes are deduplicated across the exported populations. A completed query with no activity can yield zero; missing or failed collection cannot.

## Coverage

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

**Aztec Network.** Reviewed Aztec v4, v5 and v6 rollup contracts and selected operator, governance and deposit methods. Legacy zk.money, arbitrary execution and unresolved routes remain excluded.

**Starknet.** Direct state updates and selected bridges; shared SHARP proof transactions excluded without proportional allocation.

**ZKsync Era.** Identified direct-chain settlement and bridges; shared Gateway proofs and settlement excluded.

**Hyperliquid.** Ethereum-side CCTP, Across, Wormhole and DLN routes for Hyperliquid/HyperEVM. Native Hyperliquid execution and its Arbitrum bridge excluded; no allocation of Arbitrum settlement.

**Polygon PoS.** Polygon PoS checkpoints, reviewed staking and deposits, plus decoded bridges. Sidechain grouped with other non-L2 chains; unverified exits and arbitrary state messages excluded.

**EDGE Chain.** Ethereum-side bridge activity only. EDGE is an L3 settling via Arbitrum, excluded from both synthetic group subtotals.

**Other Chains.** Selected dedicated contracts, sender-specific inboxes and/or decoded chain-specific shared bridges, as listed per source. A chain with only bridge coverage is not assigned hypothetical settlement gas.

**Shared Bridges.** CCTP, Across, Wormhole and DLN: require a known source/destination chain and reviewed method. Incoming authenticated token-only routes included; mixed settlements, shared fills and arbitrary L1 callbacks excluded.

**Codex.** Reviewed prior and current Ethereum batch inboxes, canonical bridge deposits, withdrawal proofs, dispute-game creation and decoded shared bridge routes. Batch senders and applicable inbox activation intervals are checked. Continuing submissions to the prior dedicated inbox are retained even after the registry changed its DA tracking. Arbitrary L1 finalizations and unreviewed methods remain excluded.

Lighter's included core receipts cover **16,547 of 106,212** observed deposit parent transactions and **33,958 of 34,739** withdrawal-claim parents. These are transaction counts, not gas-coverage percentages. The event populations were recollected across the complete current window.

## Acquisition, reconciliation and retained history

Verified historical observations from 2026-05-09 through the day before 2026-09-28 are retained from the preceding release. New observations cover 2026-09-28 through 2026-11-08. Newly identified recipient cohorts are additionally backfilled to 2026-05-09; their independent queries identify that full interval. No interpolation, extrapolation or native-chain gas is used. The cutoff is bound to Ethereum block 26,373,602.

New account populations are collected from Routescan and reconciled by daily gas and count against Blockchair. Pagination overlaps are deduplicated. Conflicts are checked against canonical receipt, transaction and block membership evidence. 1 simple 21,000-gas inbox transaction required an explicitly documented receipt-source exception: the receipt RPC returned an error, so actual gas-used and status records from both Routescan and Blockchair were matched, followed by the same canonical transaction and block-membership checks. Gas limits were not substituted for gas used. The exact source records and exception manifest are included in the evidence archive. Reviewed ABI methods and attribution-bearing fields determine inclusion. Successful closed settlement methods may retain opaque proof bytes without decoding their mathematical contents. Original aggregate-only cohorts retain their documented scope and receive new canonical receipt samples. Supplemental token approvals are fully enumerated and decoded. This is not a full independent recount of Ethereum.

The current acceptance certificate binds all input hashes, 365 acquired account populations, 430 aggregate queries and the separate classification and reconciliation results. The merged receipt archive is recounted against the complete current daily totals before release. Dated historical evidence describes its own earlier interval; it is not substituted for new observations.

## Interface and exports

The comparison is sorted by selected-period million Ethereum gas per day. The 7-day and 30-day views end at the snapshot cutoff; the six-month view contains 184 daily observations. Group subtotals overlap their members and are not added to exported observations. The ETH-transfer benchmark is contextual and may overlap incidental product-related movements. Do not sum all comparison rows. Ratios of lower bounds are not themselves lower bounds.

Daily chart bars show observed gas. The line is a trailing seven-day arithmetic mean, including available history before a zoomed window. Chart zoom does not change the separately labelled main comparison interval. The change metric compares the latest 30 days with the previous 30. ETH-transfer equivalents divide gas by 21,000 without comparing transaction usefulness.

CSV, JSON, all eight language views and social metadata derive from this accepted snapshot and its current scope. The bulk transaction receipt CSVs are preserved in a separate archive and are not hosted with the app or included in its source repository. receipt-index.json retains every file checksum, transaction count and exact population coverage; receipt-validation.json records the full reconciliation, bound to the accepted inputs and verifier. To repeat the receipt recount, obtain the separate archive and run the documented validation command. These ledgers include every newly included receipt and previously published core receipts. Original supplemental approvals outside those core exports remain documented in the structured dataset. No synthetic aggregate receipt is created.

The public evidence ZIP contains factual query responses, verification results and dated prior evidence. Identical canonical RPC responses are stored once by SHA-256 in current/canonical-responses.json, as exact UTF-8 response strings. current/canonical-index.json maps every original response filename to its checksum and byte length; UTF-8 encoding the corresponding string reconstructs the original bytes. Full provider response pages are preserved separately. Application source and private review records are not part of the data downloads.

## L2 aggregate classification

“All L2 rollups” and “All L2 non-rollups” are fixed cohorts by data-availability design at the end of this snapshot (2026-11-08). Rollups publish the data needed to reconstruct state to Ethereum. Non-rollups use external data availability. This distinction is not a security-stage or decentralization rating. [The classification file](/data/l2-classification.json) lists every covered L2, sources and migration notes.

Historical gas stays with the end-of-snapshot cohort, even before a migration. Every selected-period observation stays with its chain’s end-of-snapshot cohort. The totals do not measure gas consumed only while that chain operated under its current architecture. Nova and X Layer changed architecture during this window. Codex includes its earlier Ethereum batch-inbox history in its current rollup cohort. These totals therefore compare the tracked footprints of fixed cohorts, not gas consumed exclusively under each historical architecture. Chains with unverified data availability remain individual rows outside both L2 sums.

“All alt L1s” retains covered non-L2 chains, including Polygon PoS. EDGE is an L3 and is excluded from all three subtotals. Subtotals overlap their members and never become observations or receipts. The original evidence archive remains dated acquisition evidence; this classification annex is the current presentation taxonomy. Ratios of observed lower bounds are not themselves lower bounds. Execution-gas comparisons exclude blob gas and do not directly measure network effects or establish causation.
