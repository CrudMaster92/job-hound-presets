# Fortune 325 — 2026 validation

The stable `fortune-50-2026` collection advances to revision 7 with **325 ranked companies, 291 available companies, 294 installable monitors, and 34 unavailable companies**. The first 300 memberships and existing company and monitor records are preserved. Ranks 301–325 follow the [2026 Fortune 500 ranking](https://www.fortunechina.com/fortune500/c/2026-06/03/content_474100.htm).

## New scraper coverage

All 25 additions have one installable monitor. Each saved recipe returned jobs through the real JobHound scraper runtime on September 23, 2026; counts, sample titles, locations, source URLs, exact recipe hashes, and warnings are in [structured evidence](fortune-325-2026-evidence.json). One representative job URL per monitor returned HTTP 200. All 25 logo URLs returned HTTP 200 and decoded as images; Diamondback uses the official site logo because its favicon endpoint returned 404. The Workday monitors use browser extraction because the JSON adapter can omit the board name from job URLs. EchoStar, FirstEnergy, Estée Lauder, and CSX also use browser extraction; the other sources use public JSON or server-rendered HTML.

Every new monitor marks its listing as partial. The bounded first page must not be used to close unseen jobs. Fidelity National Financial, Amentum, MasTec, Reliance, and BrightSpring have explicit board or operating-company scope notes. No login, access-control bypass, local monitor installation, or schedule change was used.

## Contracts and checks

The collection schema now permits up to 500 ranked references while the install handoff remains capped at 200 selections. The browser selection test covers a 294-monitor collection with explicit 200/94 batches and rejects an oversized handoff. The catalog builds successfully to **470 companies, 441 monitors, and four collections**. All eight catalog unit tests pass, as do the manifest validation command and diff formatting check. The published catalog is generated from these source manifests; no independent UI or generated catalog copy was edited.
