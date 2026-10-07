# Large employer coverage: Canada and USA

Validated October 7, 2026 against the canonical JobHound runtime, starting from
catalog main `684d7d6`. This is a local draft, not a published catalog or an
installation into a user's monitors. No personal tracking data was changed.

The request includes government and public-sector employers. Research targeted
domestic employment, counting federal government once rather than counting its
departments again. Available disclosures mix headcount, full-time equivalents,
franchise workers and consolidated subsidiaries, and use different dates.
Consequently this draft does **not** certify an exact national top-ten ranking.
It covers ten US candidates and eleven Canadian candidates, including Canada
Post as additional coverage near the uncertain Canadian cutoff. Historic AHS
counts are especially sensitive to Alberta's healthcare restructuring.

Ten new crawlers returned current postings. Seven existing US crawlers also
returned postings and were reused without copying their recipes. Four Canadian
sources restrict access and have unavailable company records with explanations,
not fabricated installable monitors. All returned source URLs were checked
against the recipe host allowlist; representative titles and links were inspected
for employer ownership. Detailed dated samples and runtime warnings are in
[the evidence file](largest-employers-2026-evidence.json).

| Country | Employer / monitor | Change | Observed jobs | Scope and limitation |
| --- | --- | --- | ---: | --- |
| Canada | Government of Canada | New | 20 | Public GC Jobs listings; local browser required. Separate Crown, military and agency career systems excluded. Location unspecified where the listing cannot be parsed reliably. |
| Canada | Santé Québec | New | 10 | Central board and Équipe Volante Publique, not all institution boards. |
| Canada | Loblaw | New | 100 | Public Loblaw career listings; separate Shoppers and franchise sources excluded. |
| Canada | Walmart Canada | New board under existing Walmart identity | 140 | Canadian careers board. |
| Canada | Royal Bank of Canada | New | 200 | Official global RBC Workday board; includes international roles. |
| Canada | TD Bank Group | New | 200 | Official global TD Workday board; includes US and international roles. |
| Canada | Canada Post | New | 200 | Canada Post board; separate subsidiary boards such as Purolator excluded. |
| Canada | Empire Company / Sobeys | Unavailable | — | Official career source returned HTTP 403. |
| Canada | Alberta Health Services | Unavailable | — | Official career source returned HTTP 403. |
| Canada | Québec Public Service | Unavailable | — | Official recruiting portal returned HTTP 403. |
| Canada | Ontario Public Service | Unavailable | — | Job listing endpoint redirected to a CAPTCHA. |
| USA | Federal government | New | 250 | Public USAJOBS announcements; separate USPS and military channels excluded. Announcements may represent inventories or multiple vacancies. |
| USA | State of California | New | 10 | CalCareers civil service listings; local browser required. Separate UC/CSU boards excluded; location unspecified. |
| USA | State of Texas | New | 250 | HHSC, DSHS and DFPS public careers only. Other agencies and universities excluded. |
| USA | Walmart | Reused | 30 | Existing browser recipe; local browser required. |
| USA | Amazon | Reused | 999 | Existing official jobs API; global roles. |
| USA | Home Depot | Reused | 200 | Existing CareerDepot board; separate store/hourly boards excluded. |
| USA | Target | Reused | 200 | Existing Workday board. |
| USA | Kroger | Reused | 25 | Existing browser recipe; local browser required. |
| USA | FedEx | Reused | 25 | Existing public HTML recipe. |
| USA | UPS | Reused | 200 | Existing Workday board. |

Counts are bounded observations, not employer vacancy totals. Listing and detail
request counts differ because detail enrichment adds requests. Several sources
deny detail requests or omit descriptions; their valid listing records remain
usable and the evidence preserves those warnings. All new recipes explicitly
declare partial coverage so unseen jobs cannot be treated as closed. Browser
recipes remain excluded from the non-browser public collector.

## Catalog organization and runtime changes

One new **Public Sector — Canada & USA** collection references six working
sources and three unavailable employers. Commercial sources remain individually
searchable without creating more collections. Walmart Canada reuses Walmart's
existing company identity and therefore also appears in the existing Fortune
500 collection; that collection advances to revision 13 with 448 monitors.
The other seven existing monitors are unchanged.

The canonical runtime now counts the `generic_json` mapped listing array during
pagination, supports an allowlisted HTTPS posting prefix for public slug APIs,
and preserves a public browser hash route through `metadata.browser_fragment`.
The same recipe runner serves human and agent contracts. No MCP tools or
matching rules changed. Deploy the canonical runtime before publishing these
recipes, and export the collector from that runtime rather than editing its
generated copy. Version `0.1.0` alone does not distinguish patched from older
runtime builds; publication is therefore dependent on coordinated deployment.

The new USAJOBS source uses the public search endpoint without an API key.
The Texas statewide Taleo endpoints are unavailable and its replacement CAPPS
portal uses session-bound JavaScript links, so only the independently supported
public health-services board is claimed. No access restrictions were bypassed.

## Research sources and freshness

These primary sources guided the candidate pool; they do not establish a
comparable ranked table:

- [Canadian federal public service population](https://www.canada.ca/en/treasury-board-secretariat/services/innovation/human-resources-statistics/population-federal-public-service-department.html).
- [Santé Québec employer consolidation](https://sante.quebec/en/news/press-releases/sante-quebec-pres-de-200-postes-de-cadres-supprimes-depuis-sa-creation/).
- [Loblaw workforce disclosure](https://www.loblaw.ca/en/loblaw-companies-limited-announces-normal-course-issuer-bid-2025/), including franchise and associate owners.
- [Empire quarterly reports](https://www.empireco.ca/quarterly-reports), [Walmart Canada](https://www.walmartcanada.ca/about-us), and [AHS workforce overview](https://www.albertahealthservices.ca/assets/about/ops/who-we-are.html).
- [RBC 2025 sustainability report](https://www.rbc.com/our-impact/_assets-custom/pdf/RBC-2025-sustainability-report.pdf) and [TD 2025 sustainability report](https://www.td.com/content/dam/tdcom/canada/about-td/pdf/esg/2025-sustainability-report-en.pdf). Global and domestic counts must not be confused.
- [Canada Post 2025 annual report](https://publications.gc.ca/collections/collection_2026/scp-cpc/Po1-2025-eng.pdf), including temporary and part-time workers, and [Ontario public service overview](https://www.ontario.ca/page/about-ontario-public-service).
- [US OPM workforce data](https://data.opm.gov/explore-data/analytics/workforce-size-and-composition), [Census public employment data](https://data.census.gov/table/GOVSEMPTIMESERIES.GS00EMP02), and [Texas state workforce report](https://sao.texas.gov/SAOReports/ReportNumber?id=26-704). State workforce scope and FTE measures differ from company headcounts.

The shared roles manifest was inspected. Its latest
generation was October 3, 2026 at 23:19 UTC, with catalog revision `6888898`;
it is stale relative to the October 7 checks. A stale snapshot or failed source
does not mean zero matching jobs. This task does not refresh or publish the feed.

## Verification

- Canonical application: 498 pytest tests passed; web production build passed.
- New mapping regression checks cover nested-array pagination, direct slug URLs
  and rejection of prefixes outside the HTTPS host boundary.
- Catalog schema/build and unit checks validate normalized ownership, searchable
  unavailable companies, reference hashes, bundles and batch selection.
- Live source runs validate ten new and seven reused monitors. Four restricted
  sources remain explicitly blocked.

No GitHub push, PR submission or merge was performed. Public contribution
submission requires an explicit request under the project's contribution policy.
