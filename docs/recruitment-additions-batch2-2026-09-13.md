# Recruitment additions: second batch, September 13, 2026

Adds The Judge Group, Jackson Healthcare and Supplemental Health Care to recruitment collection revision 5. The collection contains 34 companies and 27 verified monitors; seven unavailable identities remain visible. Existing monitor IDs and recipes are unchanged. All three new identities were checked against existing names and aliases before creation.

| Company | Strategy | Jobs | Requests/pages | Scope |
|---|---|---:|---:|---|
| The Judge Group | generic_html / iCIMS | 14 | 2 | Internal sales, recruiting, benefits and support; listing excerpts |
| Jackson Healthcare | Workday | 31 | 33 | Parent and six staffing/search brands; descriptions enriched |
| Supplemental Health Care | playwright / Dayforce | 12 | 1 | Initial corporate recruiting, sales and client-services listing |

These are live observations through the canonical JobHound `ScraperRecipe` and `run_scraper`, not permanent counts. Every returned job has a description or excerpt and a unique HTTPS source URL. All three declare `partial_listing=true` and returned `complete=false`, so jobs outside the selected scope or pagination window are not closed. Structured evidence, timestamps, warnings, official ownership URLs and sample normalized jobs are in `recruitment-additions-batch2-2026-09-13.json`.

## Ownership and coverage

The Judge Group's [internal-careers page](https://www.judge.com/about-judge/internal-judge-careers/) links directly to `careers-judge.icims.com`. The recipe follows public iCIMS pagination up to 30 pages. The second page was empty in validation. Job descriptions identify Judge as the employer; these are not the separate general placement results.

Jackson Healthcare's [Search & Apply page](https://jacksonhealthcare.com/careers/search-apply/) links directly to its Workday tenant. The unfiltered feed returned 43 jobs, including the group's USAntibiotics manufacturing roles. The accepted recipe uses Workday's public `jobFamilyGroup` facet IDs to include only Jackson Healthcare, LocumTenens.com, Jackson & Coker Locum Tenens, Jackson Physician Search, Jackson Therapy Partners, Kirby Bates Associates and Jackson Nurse Professionals. The resulting 31 jobs match the sum of the seven selected facet counts. USAntibiotics, CareLogistics, Kimedics, Premier Anesthesia and Sullivan Healthcare Consulting categories are excluded. This is explicit selected-brand coverage; future brands require review before inclusion. No title-keyword approximation is used.

Supplemental Health Care's [corporate-careers page](https://shccares.com/corporate-careers-at-shc/) links to the Dayforce `shccares/CANDIDATEPORTAL` board. All 12 observed roles are internal recruiting, business development, sales or client services. The recipe uses the existing deterministic Dayforce browser strategy, confined to the official jobs host. It does not query the separate clinical-placement board at `jobs.shccares.com`.

Addison Group and Dexian returned HTTP 403 during direct public-page inspection. Collabera's inspected internal-career route led to contact forms; CHG's inspected HTML did not expose a usable careers link. They were not added as placeholder monitors in this batch.

No application code, installed local monitors or personal data changed.

Validation passed: normalized build (395 companies, 383 monitors overall), all eight repository tests, application bundle contract (27 recruitment monitors), and git diff --check.
