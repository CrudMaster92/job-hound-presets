# Recruitment catalog repair

The published recruitment collection had 27 companies, 16 unverified monitors,
and several incorrect regional or client-placement sources. A live audit of
all 27 recipes returned jobs from nine existing internal feeds. Twelve failed
feeds now have working replacements. Six broken or unsafe-to-attribute monitors
are withdrawn, with their company identities retained as unavailable entries.
The existing ManpowerGroup identity is also referenced from Recruitment, still
unavailable pending a supported scraper. The collection has 28 companies and
21 installable monitors, with seven explicit unavailable explanations.

## Validated replacements

All counts are observations from September 12, 2026 in America/Toronto, not
permanent expectations. Every recipe ran through the canonical JobHound
`ScraperRecipe` and `run_scraper` runtime without installing local monitors.

| Company | Strategy | Jobs | Requests/pages | Coverage |
|---|---|---:|---:|---|
| Actalent | HTML, public iCIMS | 184 | 11 | US internal jobs; listing excerpts |
| Aerotek | HTML, public iCIMS | 217 | 12 | Internal careers; listing excerpts |
| TEKsystems | HTML, public iCIMS | 132 | 8 | Internal careers; listing excerpts |
| Allegis Global Solutions | SmartRecruiters | 56 | 57 | Official North America department only |
| AMN Healthcare | Workday | 28 | 30 | Corporate careers |
| Cielo | SmartRecruiters | 70 | 71 | Global internal careers |
| Heidrick & Struggles | Workday | 40 | 43 | Global company/group internal careers |
| Spencer Stuart | Workday | 20 | 21 | Global internal careers |
| Vaco | Greenhouse | 56 | 1 | Internal recruiting and business development |
| Cross Country Healthcare | Dayforce, browser | 19 | 1 | Corporate/branch support, initial results |
| Hays | HTML | 8 | 1 | Canadian internal jobs, initial results |
| TrueBlue | Oracle, browser | 25 | 1 | Corporate/brand-office jobs, initial results |

Workday and SmartRecruiters request counts include description enrichment.
The iCIMS requests include the terminal empty page. Explicitly bounded feeds
retain `metadata.partial_listing=true` so unseen jobs are not closed.
Hays office information remains in job titles; structured location is unavailable.

## Ownership checks and unavailable entries

- AGS's official jobs page embeds the SmartRecruiters company code and department
  IDs. Its North America department is `1152964`; the API's `department` parameter
  was tested and returned only that department. The unfiltered 127-job feed
  included QuantumWork Advisory and was not accepted. Final validation returned
  56 roles, with no enrichment warnings.
- Vaco's previous source was its general placement board. The replacement
  Greenhouse board is branded Vaco LLC and contains internal recruiting,
  business-development and management roles, including Canadian roles.
- Cross Country's official corporate page points to the Dayforce board.
  Two clinical-titled records describe employee Home Visit Liaison work supporting
  caregivers, clients and branch management. Those are branch-support roles,
  not the travel/clinical placement search previously used. The recipe now
  retains location and description so that distinction is inspectable.
- **Aston Carter:** the official internal-careers link redirects to Actalent.
  Do not duplicate Actalent's jobs under Aston Carter. The Australian source
  returned zero jobs and was withdrawn.
- **Insight Global:** its internal board returned 403 in a normal browser and
  timed out in the existing confined runtime. Do not replace it with client jobs.
- **Major, Lindsey & Africa:** its official internal iCIMS link returned an empty
  response. The previous public legal-placement board is not internal employment.
- **Korn Ferry:** the old page is a 404. Its linked Tal.net board contains both
  internal and client roles. Requisition 27059, Fixed Income Product Controller,
  explicitly describes hiring for a financial-services client. Generic Korn Ferry
  boilerplate and the board's brand are insufficient ownership evidence.
- **PageGroup / Robert Walters:** official pages returned 403; the existing
  placeholder recipes returned zero jobs. No access controls were bypassed.
- **ManpowerGroup:** public Taleo RPO corporate listings were found, including
  Canadian recruiting roles. Their job links are JavaScript actions rather than
  stable detail URLs. No compatible recipe was validated. The existing identity
  is reused, with a more actionable explanation, and no guessed scraper.

Structured timestamps, per-monitor warnings and representative job source URLs
are in [the audit evidence](recruitment-audit-2026-09-12.json).

## Release and recovery

Validation passed: legacy import validator, normalized catalog build, all eight
repository tests, and `git diff --check`. The generated recruitment bundle also
passes the canonical application's `CatalogPresetManifest` contract used by
human and MCP installation paths: 21 unique verified choices, with all seven
unavailable identities excluded. Evidence counts and partial-listing flags were
checked against the final authored monitors. The regression test now requires
blocked companies to remain visible without installable placeholder recipes.

This change updates authored company, monitor and collection sources. Generated
artifacts are built only for validation. It makes no application changes and
does not update, remove or install any user's local monitor or job data.

The six withdrawn monitor IDs and last revisions are retained in the audit
evidence and Git history. A later validated repair should restore the same ID
at a higher revision, rather than create a duplicate company or monitor.
Existing installations are not silently updated by a catalog release; users
must explicitly apply a catalog recipe update through JobHound.

The repair is prepared locally. Publishing requires explicit authorization.
