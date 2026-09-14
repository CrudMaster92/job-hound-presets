# Fortune 300 — 2026 validation

The existing `fortune-50-2026` collection advances to revision 6 with **300 companies, 266 available companies, 269 monitors, and 34 unavailable companies**. All first-250 memberships, existing identities and recipes are preserved from the current main baseline. The new 50 entries retain positions 251–300 from the [2026 ranking](https://www.sheetsteps.com/data/fortune-500-companies-2026); published rank and list position remain distinct, including the prior rank-160 tie.

## Evidence and coverage

Thirty-three new recipes returned jobs through the real JobHound runtime in the final September 14 UTC validation batch. The companion evidence JSON records exact normalized recipe hashes, timestamps, counts, pages, completeness, warnings and representative source URLs. Every new recipe explicitly marks partial coverage. All returned Workday source URLs were checked for their required board segment. PPG's runtime removes duplicate source IDs; this warning remains visible and its count must not imply complete coverage.

Seventeen additions are unavailable with company-specific explanations: MGM Resorts, UHS, PulteGroup, Omnicom, Leidos, Targa, Murphy USA, Kinder Morgan, Consolidated Edison, Farmers Insurance, Casey's, Raymond James, Principal Financial, Fluor, Gap, Builders FirstSource and Stanley Black & Decker. Restrictions, transport failures and unvalidated interactive searches are not assertions that an employer is not hiring. No credentials or access-control bypasses were used.

LPL's broad feed explicitly included partner-employed advisors. Its recipe now uses observed corporate category facets and excludes Other, Sales and Employee Advisor categories; the resulting descriptions were checked for partner-employment language. This intentionally omits some direct LPL opportunities. Kyndryl includes the professional board only; ITW, EMCOR, FOX and Sonic have operating-brand or division scope notes.

All 50 logos passed HTTP checks, browser image decoding under `no-referrer`, and visual review on white cards. The generic IQVIA globe and white Sonic logo were replaced. Targa's official images failed browser decoding despite HTTP success; its exact www-host favicon decoded successfully. Official replacements also cover Devon, Corning and Tractor Supply.

## Contracts and checks

The collection-membership schema permits 300 references. Install handoffs remain capped at 200 IDs and revisions. Collections exceeding 200 eligible monitors start unselected; encoding rejects oversized handoffs rather than truncating. The version-2 full bundle and explicit 200/69 selections are validated against the real application models without installation.

Required checks: `python scripts/validate_presets.py`, `python scripts/build_catalog.py`, and `python -m unittest discover -s tests -v`. Build tests cover three 100-member pages, hashes, counts, ranks, unavailable explanations and bounded browser handoffs. All company and monitor schemas, identity uniqueness and runtime recipe hashes are preflighted before authoring the batch. No application/shared UI/Sites code, local data, installed monitors or schedules are changed.

## Lessons

- A positive count is insufficient: inspect source URLs, duplicates and who actually employs the applicant.
- Observe source-specific Workday paths and Oracle runtime hosts; do not infer tenants from names.
- Automatic browser geolocation can silently narrow coverage, as observed on Gap's search.
- Verify logos in a browser on white cards, not only by HTTP status.
- Keep collection membership and bounded handoff contracts separate as the catalog grows.

Final verification: the catalog build produced 445 companies and 416 monitors across four collections. All eight tests passed. The current application's models accepted the 269-monitor version-2 bundle and exact 200/69 selections, rejecting an oversized handoff. A normal browser showed 0 of 269 initially, selected 200 explicitly, and encoded exactly 200 with opening JobHound intercepted. All 66 independently checked representative job source URLs returned HTTP 200. All 50 logos decoded and passed visual review. The final refresh of all 33 recipes returned positive results.
