# L1 Gas Impact

L1 Gas Impact shows how much gas different apps and chains use on Ethereum. Compare them side by side, see how their use changes over time, and check the data behind each number.

## License

Original project code is licensed under the [MIT License](LICENSE). Bundled React, React DOM and Scheduler retain their MIT notices in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Provider records, cited materials, logos and artwork retain any applicable third-party rights; the software license does not relicense them.

## Technical overview

Static, prerendered React research dashboard. Snapshot: March 28–September 27, 2026 UTC. Public output is restricted to `dist/`. Read `CONTRACTS` before changing measurements or release behavior.

## Reproduce current public artifacts

Install the pinned dependencies with `npm ci --ignore-scripts`. Run `npm run build:generate`, then `python3 src/validate_release.py`, and finally `node src/static_build.mjs --seal`. Data normalization requires a checksum-bound completeness certificate; missing or changed inputs stop the build. Product, period, language and inspected date use validated native URLs. Every supported locale/product/period page has meaningful static content before hydration.

The production builder has Node but no Python. `npm run build` therefore verifies the committed, locally generated output against `data/static-build-manifest.json`, including source, data, acceptance evidence and every public file. It fails on missing, extra or changed output and changed inputs. It does not silently regenerate or accept stale pages. Reseal only after required validation. The release gate also enforces the host's 256 MiB expanded archive limit, including TAR headers and padding. The packaged archive is checked again before uploading.

Prerendered views include the leading comparison rows, all three chain summaries and the selected product's metrics, chart and breakdown; all product links remain available without JavaScript. Hydration fills the complete comparison and the closed exact-data tables. Locale strings are shared assets. Daily bars use one bounded SVG path, with display coordinates rounded to 0.01 SVG unit; all gas calculations and displayed numeric readings retain their original precision.

`node src/check_theme.cjs` verifies theme precedence, storage failure and palette contrast. `node src/check_view_state.mjs` checks route restoration, custom chart windows, per-period descending sorting, view-only group totals and missing-data semantics. The private release review records actual browser desktop/mobile viewport checks; automated structural checks do not stand in for visual inspection.

## Evidence storage

The 80 compressed transaction receipt CSVs (202.6 MB) are preserved in the separate `l1-gas-impact-receipts.zip` archive. They accounted for 90.2% of public data bytes and are excluded from this repository and the hosted app. The repository retains every accepted input, daily CSV and JSON export, compact provenance ZIP, receipt index, file checksum and full reconciliation certificate. Displayed measurements are unchanged.

`python3 src/validate_release.py` checks the compact release and the prior full receipt reconciliation against exact accepted-input, receipt-metadata and verifier hashes. This is certificate verification, not a fresh receipt recount. To repeat all 4,481,096 receipt checks, extract the separate archive and run `python3 src/validate_release.py --receipt-dir /path/to/extracted/archive`. Changed inputs, receipt metadata or verifier invalidate the certificate. A research refresh must preserve and fully reconcile a new separate archive with `python3 src/compact_evidence.py --receipt-dir /path/to/receipt-work --archive-path /path/outside/repo/l1-gas-impact-receipts.zip` before release.

The repository ZIP contains the current source and sealed static output without Git history. For the initial GitHub push, extract it into a fresh directory and initialize a new Git repository there. Reusing the historical checkout would retain old receipt blobs in Git history even after their working files are removed. Keep bulk archives outside the repository.

## Research refresh

Use a new research directory for each fixed UTC snapshot and preserve raw responses. ABI research dependencies: `eth-abi==5.2.0`, `eth-utils==5.3.1`, `pycryptodome==3.23.0`. These are not runtime application dependencies.

The historical `stage_research.py` and `build_evidence.py` scripts accept `--research-dir /path/to/research`; their default is the repository's `research/` directory. The original acquisition archives are preserved separately. The accepted inputs and compact generated exports needed to reproduce the app are included in this repository; a fresh receipt recount additionally requires the separate receipt archive.

For this snapshot, `acquire_refresh.py` collects the September 15–27 delta against the restored historical research. `verify_refresh.py` independently resolves conflicting receipts and decodes supplemental populations. `sample_refresh.py` checks aggregate-only populations against canonical receipts. `classify_refresh.py` reconciles and classifies core contract receipts. `stage_refresh.py` retains the validated historical overlap, stages accepted records and rebuilds receipt exports and Lighter event coverage. Run `normalize.py`, `build_refresh_evidence.py`, and `build_site.py` in that order to synchronize data, provenance and UI.

The September 29 expansion uses `acquire_coverage.py`, `coverage_decode.py`, `classify_coverage.py`, `stage_coverage.py` and `build_coverage_evidence.py`. Its curated catalogue and original responses are preserved in dated research archives. Full account histories are reconciled against independent daily aggregates; disputed blocks are resolved using canonical receipt, transaction and block membership evidence. `resolve_coverage_disputes.py` and `repair_coverage.py` retain those corrections. The latter reclassifies only changed records and rebuilds every accepted total and hash-uniqueness check. Partial reclassification requires an explicit account list covering every affected decoder branch and checksummed reuse of unchanged cohorts.

The accepted snapshot has 71 measured entries. Solana and other non-L2 chains measure Ethereum-side activity in Ethereum receipt gas units, never native-chain gas. Earlier standalone Solana scripts remain historical reproduction material. The expanded receipt pipeline replaces overlapping CCTP/Across populations, with exact explanations for stricter attribution exclusions. Oversized proof calldata is retained once in immutable response pages and referenced by compact ledgers; acquisition maintains a 3 GiB free-space reserve and bounded request, time, retry and pagination costs.

Run normalization, current evidence generation, and the site build after staging. The three synthetic chain rows exist only in `comparisonRows`; they never enter accepted observations or exports. There is no combined L1-app summary. Product taxonomies exclude the EDGE L3 from every group total. All aggregate names use the same italic treatment and align with ordinary names. Row surfaces remain neutral, and primary comparison names are not underlined. Chart controls use native React/SVG with at most 184 observations and cached formatters; no chart dependency is added.

Original expansion scripts and dated derived summaries are historical reproduction material. Current acceptance is defined by `data/inputs.json` and its bound verification certificate. Public provenance contains factual source data and methods, not application source, private review notes or credentials.

## Release review

Check all supported products, 7/30/six-month periods, eight locales, deep links, Back/Forward, keyboard interaction, enlarged text, responsive layouts, System/Light/Dark, no-JS content, social framing, numeric exports and archive confidentiality. Inspect chart tooltip, keyboard, drag zoom, dates and restoration, plus ordinary sorting of synthetic rows in every interval. The publication gate definition, browser evidence and policy assessment remain private and are bound to the candidate revision. Release authority is assessed separately from technical readiness.

The three comparison subtotals split covered L2s by end-of-snapshot data availability and retain the other-L1 cohort. `data/l2-classification.json` is the dated, sourced classification; unknown designs remain outside both L2 sums. Historical observations stay with fixed cohorts, including observations before architecture migrations. `src/aggregate_classification.py` validates complete classification coverage and publishes the current methodology annex without changing original receipt evidence.
