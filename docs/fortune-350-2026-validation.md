# Fortune 350 — 2026 validation

The stable `fortune-50-2026` collection advances to revision 8 with **350 ranked companies, 315 available companies, 318 installable monitors, and 35 unavailable companies**. The first 325 memberships and their existing company and monitor records are preserved. List positions 326–350 follow the [2026 Fortune 500 ranking](https://www.fortunechina.com/fortune500/c/2026-06/03/content_474100.htm); the published list has a tie at rank 350, so Huntington Bancshares follows this 25-company batch.

## New scraper coverage

Twenty-four of the 25 additions have one verified monitor. Each exact saved recipe returned company-owned jobs through the real JobHound runtime on September 24, 2026. The [structured evidence](fortune-350-2026-evidence.json) records strategy, observed count, pages, completeness, warnings, recipe hash, representative titles, locations, and source URLs. A representative job URL for every new monitor returned HTTP 200. All 25 logo URLs returned HTTP 200 and decoded as images.

Sempra is included as **unavailable** with no monitor. Its official headquarters board exposes listings through an ADP session-token request, while the listing cards do not expose stable direct job links. No safe reusable recipe passed validation. This limitation is visible in the company and collection data.

Every new monitor marks its listing as partial, so unseen jobs must not be closed based on a bounded run. ServiceNow's accessible SmartRecruiters listing omits location data, making city matching unavailable for that monitor. Other board-scope and location caveats are recorded in individual verification warnings. No login, access-control bypass, local monitor installation, or schedule change was used.

## Contracts and checks

The collection remains within the 500-member schema limit. The install handoff remains capped at 200 selections, and the browser selection test covers explicit 200/118 batches for 318 monitors. The catalog builds to **495 companies, 465 monitors, and four collections**. The manifest validator, catalog build, eight unit tests, browser selection test, recipe integrity check, and diff formatting check pass. Generated catalog output was used only for validation and is not included as authored source.
