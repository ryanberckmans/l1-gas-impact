# L1 Gas Impact

Read `CONTRACTS` before edits. Keep data collection, classification, and release validation separate. Public files are restricted to `dist/`; do not publish private research notes, source scripts, credentials, or contracts.

`src/normalize.py` assembles explicitly accepted source populations and checks dates, duplicate aggregate keys, integer gas, and bucket reconciliation. `src/build_site.py` prerenders every supported product/period view in eight locales. `src/validate_release.py` is the publication gate. Any new source requires a documented exclusive-attribution rule and a check against overlapping populations.

This is a fixed research snapshot, not a live chain indexer. Do not present unresolved or missing scope as zero. Preserve original provider responses and correction records when updating the evidence.

Generate and validate locally with `npm run build:generate` and `python3 src/validate_release.py`, then seal with `node src/static_build.mjs --seal`. Production `npm run build` verifies all committed output and its input hashes without requiring Python. Never reseal changed measurements or UI to bypass their required review.

Scope and naming changes apply to the complete public deliverable: page copy, every locale, social-card artwork, Open Graph/X metadata, image alt text, and public data guidance. Metadata derives from the page headline and intro. `src/social-card.json` binds the manually reviewed English card to those source strings and its image checksum; re-review the actual image before updating that record. Use a new image URL for changed artwork to reduce stale social caches. Preserve factual historical provider records.

Bulk receipt CSVs belong in a separate archive, outside Git and `dist/`. Keep compact indices, hashes and reconciliation evidence in the release. A cached full receipt reconciliation is reusable only when its accepted-input, receipt-metadata and verifier bindings match; changed bindings require the separate archive and a new full recount. Do not claim a fresh recount when only certificate verification ran.
