# Fortune 375 — 2026 validation

The stable `fortune-50-2026` collection advances to revision 9 with **375 ranked companies, 339 available companies, 342 installable monitors, and 36 unavailable companies**. The first 350 memberships and their existing company and monitor records are preserved. List positions 351–375 follow the [2026 Fortune 500 ranking](https://www.fortunechina.com/fortune500/c/2026-06/03/content_474100.htm). Huntington Bancshares occupies list position 351 at published rank 350 because of the rank tie.

## New scraper coverage

Twenty-four of the 25 additions have one verified monitor. Each exact saved recipe returned company-owned jobs through the JobHound scraper runtime on September 24, 2026. The [structured evidence](fortune-375-2026-evidence.json) records strategy, observed count, page count, completeness, warnings, recipe hash, representative titles, locations, and direct source URLs. All 25 logos returned HTTP 200 and decoded as images. Twenty-three representative job URLs returned HTTP 200. Darden's returned HTTP 202 to a plain request; its browser page displayed the expected title and job description.

Wayfair is included as **unavailable** with no monitor. Its official careers board returned HTTP 429 during validation, and no safe live alternative passed verification. The accessible SmartRecruiters record was stale and was not used. No access-control bypass was used.

Every new monitor marks its listing as partial, so unseen jobs must not be closed based on a bounded run. Darden's board covers its Restaurant Support Center, Yum China's board covers restaurant-management roles posted in the last 30 days, AES uses its U.S. Workday board, and Hilton's Oracle board does not represent all franchise hiring. These limits appear in monitor warnings and collection notes. No local monitor installation or schedule change was made.

## Contracts and checks

The collection stays within the 500-member schema limit. The install handoff remains capped at 200 selections; the browser test covers 200/142 batches for 342 monitors. The catalog builds to **520 companies, 489 monitors, and four collections**. The manifest validator, catalog build, eight unit tests, browser selection test, recipe-hash audit, source/link check, and diff formatting check pass. Generated catalog output was used only for validation and is not included as authored source.
