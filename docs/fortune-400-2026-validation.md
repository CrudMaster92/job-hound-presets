# Fortune 400 — 2026 validation

The stable `fortune-50-2026` collection advances to revision 10 with **400 ranked companies, 358 available companies, 361 installable monitors, and 42 unavailable companies**. The first 375 memberships and their existing company and monitor records are preserved. Positions 376–400 follow the [2026 Fortune 500 ranking](https://www.fortunechina.com/fortune500/c/2026-06/03/content_474100.htm).

## New coverage

Nineteen of the 25 additions have a verified monitor. Each saved recipe returned company-owned jobs through JobHound's scraper runtime on September 24–25, 2026. The [structured evidence](fortune-400-2026-evidence.json) records strategy, count, pages, completeness, recipe hash, warnings, and representative direct job URLs. Every new monitor marks its listing as partial so a bounded run cannot close unseen jobs. Gold.com's current official listing is for its Stack's Bowers Galleries subsidiary; the Wabtec and Expeditors SmartRecruiters landing pages expose bounded subsets without per-job cities. Oscar's public Greenhouse feed is mapped without descriptions because one source salary string breaks the current salary normalizer.

Six additions are visible as **unavailable**, each with a specific reason and no installable monitor: Equitable Holdings, Caesars Entertainment, Thrivent Financial, Westlake, Lululemon, and FM. Their public boards either presented access challenges, failed to load normally, or did not yield a validated portable listing recipe. These states do not imply that the companies have no vacancies. No access controls were bypassed.

All 25 logo URLs returned HTTP 200 and decoded in a browser. A contact sheet was visually reviewed, with official SVG replacements for Baxter, eBay, Quest Diagnostics, and The Andersons. All 19 representative job URLs returned HTTP 200 with HTML content. Job counts are point-in-time observations, not expected future counts. No local monitor installation or schedule change was made.

## Contracts and checks

The collection remains within the 500-member schema limit. Install handoffs remain capped at 200 selections; the browser test covers explicit 200/161 batches for 361 monitors. The catalog builds to **545 companies, 508 monitors, and four collections**. The manifest validator, catalog build, eight unit tests, browser selection test, recipe hash audit, source-link checks, and diff formatting check pass. Generated catalog output was used for validation and is not included as authored source.
