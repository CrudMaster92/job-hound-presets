# Fortune 150 — 2026 expansion

The existing Fortune preset now contains ranks 1–150. Its display name is **Fortune 150 — 2026**, revision 3. The stable `fortune-50-2026` ID preserves saved links and references.

## Coverage and validation

- Added 50 company identities and logos, plus 48 reusable monitors validated through the canonical JobHound scraper runtime on September 6, 2026.
- The whole collection contains **150 companies, 142 installable companies, 145 monitors, and eight unavailable placeholders**. CBRE and Lithia join the six previously documented exceptions.
- All 50 new logo URLs returned HTTP 200, then loaded successfully in a normal browser: **50 loaded, zero failures**. The contact sheet was visually inspected. Northwestern Mutual, BNY and Dow required replacement logo URLs.
- Every new monitor records bounded/partial coverage. Job counts are point-in-time observations, not guarantees of exhaustive inventory.
- Ranking order extends the same [2026 ranking source](https://www.sheetsteps.com/data/fortune-500-companies-2026). Per-company Fortune profile links, recipe hashes, timestamps, job counts, pages, warnings and sample jobs are in [the evidence report](fortune-150-2026-evidence.json).
- Tests cover both collection member pages (100 + 50), all ranks, unique identities, logos, integrity hashes, the 145-monitor bundle and non-installable unavailable entries. Human browsers and agent consumers use these same generated catalog artifacts.

## Exceptions and limitations

**CBRE:** its public Avature board displays jobs in a normal browser, but plain HTTP returns 202 and the restricted unattended browser run did not produce the required job cards. It remains visible with a scraper-repair explanation and no installable recipe.

**Lithia:** its published US Workday feed returned HTTP 422, the board page returned HTTP 500, and its older iCIMS portal listed no jobs. The UK board displayed jobs interactively but also failed unattended validation. It remains visible with a scraper-repair explanation; this does not mean Lithia is not hiring.

**Cummins:** the representative job returned HTTP 404 even though the ordinary browser rendered its complete, matching job description. It is a working browser destination with an incorrect server status. This behavior is recorded in the monitor warnings.

**Coupang:** the official page embeds the `coupang` Greenhouse board. The deterministic Greenhouse feed returned 689 jobs. Plain HTTP access to the branded job page was restricted, but a representative feed URL redirected to the correct job description in a normal browser.

**Philip Morris:** the employer includes talent-pool postings alongside open roles. Some multi-location results expose aggregate labels rather than individual cities; this limitation is recorded in its monitor warnings.

## Patterns that helped at this scale

- Follow an official application link before constructing an ATS recipe. Salesforce and Dow exposed working Workday boards behind custom careers pages. Use the employer's main board when campus or subsidiary boards are also linked.
- Keep both Eightfold patterns: the newer public `pcsx/search` feed and the older public `apply/v2/jobs` feed. Netflix uses the older interface; selecting the endpoint used by its own page resolved the failed first candidate.
- Shared HTML and browser patterns help with SuccessFactors, TalentBrew, BrassRing, Oracle, and Jobsyn, but each tenant still needs independent execution and ownership checks.
- Validate rendered logos as well as HTTP responses. A successful download alone does not prove that a logo embeds correctly.
- Test real job destinations in addition to extraction. Server status, branded-page access and browser rendering can differ.
- Keep explicit unavailable metadata instead of publishing broken recipes. Pagination tests become essential once collections exceed 100 members.

## Publication

A push to GitHub main triggers catalog validation/build and automatic GitHub Pages publication. Sites reads the live catalog, so this data-only expansion requires no separate Sites code deployment. Refresh the Presets page to load the new revision.
