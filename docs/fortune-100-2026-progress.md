# Fortune 100 expansion — catalog coverage and validation

This expansion preserves the existing first 50 companies and adds the missing companies from ranks 51–100 of the [2026 ranking](https://www.sheetsteps.com/data/fortune-500-companies-2026). Collections have not been changed or published.

## Catalog coverage

- All 100 ranked companies now have catalog entries. Of the 50 additions, 44 have recipes that returned fresh, company-owned jobs through the canonical JobHound runtime.
- The six companies without a safe working recipe remain discoverable with a structured unavailable status, reason code, human-readable explanation, last-checked time, and logo. They have no monitor recipe, so users and agents cannot accidentally install a source known to be broken.
- All 50 new logo URLs returned successfully and displayed in a normal browser (50 loaded, no failures). The logo contact sheet was visually inspected; Allstate was corrected to its official corporate logo after an embeddability failure.
- Every new monitor is explicitly marked partial. Positive bounded runs prove that a monitor works; they do not claim exhaustive global inventory.
- General Dynamics uses a bounded official General Dynamics Electric Boat source because the corporate aggregator is protected by Azure WAF. The monitor records the business unit in recipe metadata.
- No collections, schedules, user data, credentials, or authentication material were changed.

## Unavailable company explanations

Six companies do not yet have a recipe that meets the verification standard. JobHound shows these explanations in Presets company search:

- **Progressive** and **HCA Healthcare:** their visible TalentBrew pages return real listings, but unattended requests receive managed Cloudflare challenges. JobHound does not retain challenge cookies or bypass that control.
- **Delta Air Lines:** the official Avature jobs URL currently returns an empty HTTP 202 maintenance response; Delta's own careers page warns that the careers site is undergoing maintenance.
- **Publix:** its current first-party jobs site renders listings for US search crawlers but serves a regional unavailability page in the local Toronto browser. The legacy BrassRing board loads interactively but did not produce jobs in JobHound's fresh background run.
- **American Airlines:** the first-party search renders 10 jobs interactively. Its published SuccessFactors endpoint requires a dynamic CSRF token, and the background browser did not render the cards. Tokens and cookies are intentionally excluded from recipes.
- **Enterprise Products Partners:** the official Taleo page exposes listings, but job anchors are JavaScript actions with `#` URLs. A recipe would return broken links, so it was not marked verified.

## Patterns worth retaining

- Prefer server-rendered HTML or public JSON before browser automation. Uber became reliable once JobHound preserved meaningful trailing slashes on request URLs.
- Treat trailing slashes as request semantics. Some servers return a full listing for `/jobs/` and 403 for `/jobs`; canonical display URLs may still remove cosmetic slashes.
- Follow official application links to the ATS. Workday also appears on `myworkdaysite.com`, not only `myworkdayjobs.com`.
- Brand-hosted Oracle pages fetch jobs from separate tenant hosts. Allow only hosts observed in the public site, then validate with JobHound's restricted runtime.
- Shared ATS structure scales well: one bounded selector pattern covered ADM and Performance Food Group on BrassRing, while Publix still required independent validation because tenants can behave differently.
- Business-unit sources are useful fallbacks for corporate aggregators when ownership is explicit and the recipe records its limited scope.
- The current generic JSON paginator recognizes only certain top-level arrays. Nested feeds stop after one page; configured page limits alone do not prove pagination.
- Logo downloads are insufficient verification. Render every logo in a browser because an HTTP 200 asset can still reject embedding.
