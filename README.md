# L1 Gas Impact

L1 Gas Impact shows how much gas different apps and chains use on Ethereum. Compare them side by side, see how their use changes over time, and check the data behind each number.

## License

Original project code is licensed under the [MIT License](LICENSE). Bundled React, React DOM and Scheduler retain their MIT notices in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Provider records, cited materials, logos and artwork retain any applicable third-party rights; the software license does not relicense them.

## Technical overview

Static, prerendered React research dashboard. Snapshot: May 9–November 8, 2026 UTC. Public output is restricted to `dist/`. Read `CONTRACTS` before changing measurements or release behavior.

## Reproduce current public artifacts

Install the pinned dependencies with `npm ci --ignore-scripts`. Run `npm run build:generate`, then `python3 src/validate_release.py`, and finally `node src/static_build.mjs --seal`. Data normalization requires a checksum-bound completeness certificate; missing or changed inputs stop the build. Product, period, language and inspected date use validated native URLs. Every supported locale/product/period page has meaningful static content before hydration.

The production builder has Node but no Python. `npm run build` therefore verifies the committed, locally generated output against `data/static-build-manifest.json`, including source, data, acceptance evidence and every public file. It fails on missing, extra or changed output and changed inputs. It does not silently regenerate or accept stale pages. Reseal only after required validation. The release gate also enforces the host's 256 MiB expanded archive limit, including TAR headers and padding. The packaged archive is checked again before uploading.

Prerendered views include the leading comparison rows, all three chain summaries and the selected product's metrics, chart and breakdown; all product links remain available without JavaScript. Hydration fills the complete comparison and the closed exact-data tables. Locale strings are shared assets. Daily bars use one bounded SVG path, with display coordinates rounded to 0.01 SVG unit; all gas calculations and displayed numeric readings retain their original precision.

`node src/check_theme.cjs` verifies theme precedence, storage failure and palette contrast. `node src/check_view_state.mjs` checks route restoration, custom chart windows, per-period descending sorting, view-only group totals and missing-data semantics. The private release review records actual browser desktop/mobile viewport checks; automated structural checks do not stand in for visual inspection.

## Evidence storage

The 79 compressed transaction receipt CSVs, containing 4,634,765 receipts, are preserved in the separate `l1-gas-impact-receipts-2026-11-08.zip` archive (209.3 MB). They are excluded from this repository and the hosted app. The repository retains every accepted input, daily CSV and JSON export, compact provenance ZIP, receipt index, file checksum and full reconciliation certificate. Full original provider response archives are preserved separately.

`python3 src/validate_release.py` checks the compact release and its full receipt reconciliation against exact accepted-input, receipt-metadata and verifier hashes. This is certificate verification, not a fresh receipt recount. To repeat all 4,634,765 receipt checks, extract the separate archive and run `python3 src/validate_release.py --receipt-dir /path/to/extracted/archive`. Changed inputs, receipt metadata or verifier invalidate the certificate. A research refresh must preserve and fully reconcile a new separate archive with `python3 src/compact_evidence.py --receipt-dir /path/to/receipt-work --archive-path /path/outside/repo/l1-gas-impact-receipts.zip` before release.

The public evidence ZIP deduplicates identical canonical RPC responses by SHA-256. `current/canonical-index.json` maps original response filenames to checksums and byte lengths; `current/canonical-responses.json` contains the exact UTF-8 response strings. Encoding each string as UTF-8 reconstructs the original bytes. The release validator checks every mapping and digest.

Clone the existing repository for development and preserve its Git history when publishing updates. Accepted inputs and sealed static output are versioned together. Keep bulk receipt and raw-provider archives outside the repository.

## Research refresh

Use a new research directory for each fixed UTC snapshot and preserve raw responses. ABI research dependencies: `eth-abi==5.2.0`, `eth-utils==5.3.1`, `pycryptodome==3.23.0`. These are not runtime application dependencies.

The historical `stage_research.py` and `build_evidence.py` scripts accept `--research-dir /path/to/research`; their default is the repository's `research/` directory. The original acquisition archives are preserved separately. The accepted inputs and compact generated exports needed to reproduce the app are included in this repository; a fresh receipt recount additionally requires the separate receipt archive.

The current pipeline is `refresh_window.py`. It uses a new dated research directory, the preceding accepted snapshot, and its preserved core/coverage catalogues. `prepare` pins a 184-day UTC window, block boundaries and baseline hashes. `extend` incorporates the separately reviewed `data/cohort-updates.json`, retaining retired contracts and backfilling newly tracked recipients over the whole window. `collect` resumes immutable aggregate and receipt caches with bounded concurrency. `events` enumerates Lighter event parents over the full window. `supplements` enumerates token approvals, partitioning larger populations by date within provider pagination limits. `classify` reconciles independent daily gas/count totals, resolves conflicting indexed receipts against canonical block membership, and applies the reviewed ABI rules.

An optional `python3 src/prefetch_canonical_rpc.py "$REFRESH_DIR" "$BASELINE_RESEARCH"` phase fills canonical evidence caches from PublicNode before classification. It uses one bounded batch at a time, spaces batches for an average budget of five logical calls per second, and caps the dated research run at 5,000 calls. Missing receipts remain unresolved for the normal verifier; only complete receipt, transaction and block triples can pass canonical checks. Raw batch responses and per-cache provenance are preserved. This phase may accompany the Routescan verifier because it uses a separate provider; never run two prefetch processes together. `python3 src/check_rpc_batches.py` checks response-ID integrity and failure handling.

For a documented, query-specific receipt-RPC failure, an explicit per-hash manifest may bind independent Routescan and Blockchair records of actual gas used. This narrow path accepts only matching 21,000-gas, zero-value, empty-input inbox calls and still requires canonical transaction and block-membership checks. It does not derive gas used from gas limits. The current evidence archive identifies the source exception and all original records. `python3 src/check_canonical_fallback.py` exercises conflicting and tampered evidence.

```sh
python3 src/refresh_window.py prepare --research-dir "$REFRESH_DIR" --prior-refresh "$PRIOR_CORE" --prior-coverage "$PRIOR_COVERAGE" --baseline-research "$BASELINE_RESEARCH" --through 2026-11-08
# Repeat the command with modes: extend, collect, events, supplements, classify, in that order.
python3 src/stage_window.py "$REFRESH_DIR" --prior-receipts "$PRIOR_RECEIPTS_ZIP"
python3 src/normalize.py --bind-classification
python3 src/build_window_evidence.py "$REFRESH_DIR"
python3 src/compact_evidence.py --receipt-dir "$REFRESH_DIR/receipt-work" --archive-path "$NEW_RECEIPTS_ZIP"
python3 src/build_site.py
python3 src/validate_release.py --receipt-dir "$REFRESH_DIR/receipt-work"
node src/check_view_state.mjs
node src/static_build.mjs --seal
npm run build
```

`stage_window.py` retains only the verified historical overlap, merges the new observations, and reconstructs the detached receipt ledgers. The new receipt set must reconcile to the entire current snapshot. `--bind-classification` explicitly binds a classification reviewed for the new cutoff to the freshly calculated snapshot ID; ordinary normalization refuses stale classification. Keep all raw research and receipt archives outside the repository. The provider response cache belongs to one pinned window and must not be reused for another. The commands above run sequentially. The optional `supplements` phase can overlap receipt collection after all aggregate queries finish: it uses Blockchair and a separate usage checkpoint while receipts use Routescan. Wait for both phases before classification. Subsequent phases merge the cumulative provider budgets; never run two phases against the same provider concurrently. This is a manual, fixed-snapshot workflow; no daily automation or live browser API collection is configured.

The September 29 expansion uses `acquire_coverage.py`, `coverage_decode.py`, `classify_coverage.py`, `stage_coverage.py` and `build_coverage_evidence.py`. Its curated catalogue and original responses are preserved in dated research archives. Full account histories are reconciled against independent daily aggregates; disputed blocks are resolved using canonical receipt, transaction and block membership evidence. `resolve_coverage_disputes.py` and `repair_coverage.py` retain those corrections. The latter reclassifies only changed records and rebuilds every accepted total and hash-uniqueness check. Partial reclassification requires an explicit account list covering every affected decoder branch and checksummed reuse of unchanged cohorts.

If a refresh reports daily differences, run `assess_coverage_disputes.py "$REFRESH_DIR" "$BASELINE_RESEARCH"` followed by `resolve_coverage_disputes.py` with the same arguments, then repeat classification. The assessment covers both expanded and original core accounts. Canonical corrections can add omitted transactions or reject proven noncanonical index entries; they do not alter original response pages. Staging requires all daily counts and gas totals to reconcile and binds the correction evidence into the new snapshot certificate.

The accepted snapshot has 71 measured entries. Solana and other non-L2 chains measure Ethereum-side activity in Ethereum receipt gas units, never native-chain gas. Earlier standalone Solana scripts remain historical reproduction material. The expanded receipt pipeline replaces overlapping CCTP/Across populations, with exact explanations for stricter attribution exclusions. Oversized proof calldata is retained once in immutable response pages and referenced by compact ledgers; acquisition maintains a 3 GiB free-space reserve and bounded request, time, retry and pagination costs.

Run normalization, current evidence generation, and the site build after staging. The three synthetic chain rows exist only in `comparisonRows`; they never enter accepted observations or exports. There is no combined L1-app summary. Product taxonomies exclude the EDGE L3 from every group total. All aggregate names use the same italic treatment and align with ordinary names. Row surfaces remain neutral, and primary comparison names are not underlined. Chart controls use native React/SVG with at most 184 observations and cached formatters; no chart dependency is added.

Original expansion scripts and dated derived summaries are historical reproduction material. Current acceptance is defined by `data/inputs.json` and its bound verification certificate. Public provenance contains factual source data and methods, not application source, private review notes or credentials.

## Release review

Check all supported products, 7/30/six-month periods, eight locales, deep links, Back/Forward, keyboard interaction, enlarged text, responsive layouts, System/Light/Dark, no-JS content, social framing, numeric exports and archive confidentiality. Inspect chart tooltip, keyboard, drag zoom, dates and restoration, plus ordinary sorting of synthetic rows in every interval. The publication gate definition, browser evidence and policy assessment remain private and are bound to the candidate revision. Release authority is assessed separately from technical readiness.

The three comparison subtotals split covered L2s by end-of-snapshot data availability and retain the other-L1 cohort. `data/l2-classification.json` is the dated, sourced classification; unknown designs remain outside both L2 sums. Historical observations stay with fixed cohorts, including observations before architecture migrations. `src/aggregate_classification.py` validates complete classification coverage and publishes the current methodology annex without changing original receipt evidence.
