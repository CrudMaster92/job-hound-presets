# Fortune 250 — 2026 validation

Validated September 12, 2026 against main `e5e931effdb2646dca4e71c0345471368fd0ab42`.

The existing `fortune-50-2026` collection advances to revision 5 with 250 companies, 233 available companies, 236 installable monitors and 17 unavailable companies. The first 200 memberships and their authored identities and recipes are preserved. The next 50 positions retain source order and published ranks from the [2026 ranking](https://www.sheetsteps.com/data/fortune-500-companies-2026), including the existing rank-160 tie.

All 42 new monitors returned positive results through the actual JobHound runtime on September 12. The companion evidence JSON records normalized recipe hashes, timestamps, counts, pages, completeness, warnings and sample URLs. Every new feed is explicitly partial; division-specific boards have scope notes. Counts describe the observed run, not complete hiring coverage.

Eight new companies remain unavailable with specific explanations: CDW, BJ's Wholesale, Cognizant, ADP, Parker-Hannifin, American Family ManpowerGroup and General Mills. Interactive access did not establish a working deterministic scraper. ManpowerGroup staffing-client vacancies were excluded from corporate employment coverage. The original nine unavailable companies retain their explanations.

All 50 logos returned HTTP 200, decoded in a browser under the catalog's no-referrer policy and passed visual inspection on white cards. Official replacement assets were used for Fiserv, Ameriprise, Lincoln and Steel Dynamics.

## Contracts and verification

Collection membership permits 250 companies. The generated version-2 bundle supports 236 monitors; the legacy version-1 importer remains unchanged. Human and structured agent handoffs remain capped at 200 IDs and revisions. The catalog browser starts collections larger than 200 eligible monitors unselected. Encoding rejects oversized selections instead of silently truncating them. Regression checks cover exact 200/36 batches, empty and oversized rejection, and smaller-collection default selection.

Preflight validates all 50 identities, 42 monitor schemas, exact runtime recipe hashes and first-200 preservation before packaging. Required catalog checks are `scripts/validate_presets.py`, `scripts/build_catalog.py` and unittest discovery. The build tests cover three member pages (100/100/50), hashes, 236-monitor bundles, unavailable states and rank order. Local JobHound data, installed monitors and schedules are untouched.

## Scaling lessons

- Keep collection size, versioned bundle contracts and handoff limits distinct. Never silently discard selections.
- Use observed ATS configuration: Avnet required an explicit Workday board path, SAP boards required their career runtime hosts, and AutoZone required its Oracle tenant host.
- Verify browser logo decoding as well as HTTP status, and scraper execution as well as interactive page access.
- Preflight the entire batch before promoting authored files; retain explicit partial and division coverage notes.

General Mills was withheld after repeated detail-enrichment failures left a job URL without the Workday board segment. Positive counts alone did not pass the source-link check.


Final local verification: catalog build produced 389 companies and 383 monitors across four collections; all eight unittest cases passed. The actual application's version-2 bundle model accepted all 236 Fortune monitors, its selection model accepted exact 200/36 batches and rejected 236 selections. A normal browser showed 0 of 236 initially, selected 200 explicitly and encoded exactly those 200 with opening JobHound intercepted. All sampled source links returned HTTP 200 except Aramark and Carvana (HTTP 403 to plain HTTP); their normal browser scrapers returned valid job links. All returned Workday URLs in the published batch include the required board segment.
