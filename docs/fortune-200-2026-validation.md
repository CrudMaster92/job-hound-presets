# Fortune 200 — 2026 expansion

The stable collection `fortune-50-2026` is now **Fortune 200 — 2026**, revision 4: 200 company identities, 191 companies with 194 installable monitors, and nine unavailable companies with explanations. The previous 150 memberships are preserved.

## Validation

The 50 additions include 49 recipes executed through the real JobHound runtime. Each returned company-owned jobs; exact recipe hashes, timestamps, counts, pages, warnings and representative URLs are recorded in [the evidence report](fortune-200-2026-evidence.json). All new recipes declare partial coverage. Workday feeds are bounded to 20 listings with up to 20 detail fetches so job URLs and descriptions are enriched. These are point-in-time checks, not a guarantee of complete or permanent coverage.

All 50 new logo URLs passed HTTP checks and browser decoding, followed by visual review. Official replacements resolved broken or unsuitable favicons, including a white Marriott logo that disappeared on white cards.

The ranking follows the [published 2026 table](https://www.sheetsteps.com/data/fortune-500-companies-2026). It lists Applied Materials and Hartford at tied rank 160; the first 200 companies retain source order, including Hartford in position 161. Individual Fortune profile sources are in the evidence report.

## Coverage limitations

- **Ross Stores:** its public search returns jobs, but clickable rows expose URLs through `data-href`, while its JSON response separates job identifiers from title-based URLs. The current portable recipe format cannot reliably express this extraction. Ross stays visible with a repair explanation and no installable monitor. It is hiring.
- **PBF Energy:** an unfiltered posting caused salary normalization to fail, leaving an unusable unenriched Workday URL. The published monitor is explicitly an engineering-keyword feed; every returned job passed detail enrichment. It does not cover all PBF roles.
- **Amphenol:** covers the High Speed and Commercial Products Group. Other business units hire separately.
- **Booking Holdings:** bounded to the first holding-company listing in each category, excluding subsidiary boards. A sample detail rejected plain HTTP but rendered the correct role in a normal browser.
- **McDonald's:** the small legacy SmartRecruiters feed includes a franchise opportunity and exposes public job JSON source links. It is not complete corporate or restaurant coverage.
- **Block:** uses the HTTPS branded browser listing with its official asset CDN. The underlying Greenhouse feed published HTTP job URLs.
- **KKR:** maps the public Greenhouse JSON directly because null metadata breaks the standard adapter for this board.

The eight earlier unavailable companies remain unchanged: Progressive, HCA Healthcare, Delta, Publix, American Airlines, Enterprise Products, CBRE and Lithia.

## Patterns for growing the catalog

1. Discover the ATS from official careers and application links. Reuse adapter patterns, but validate each tenant independently.
2. Validate all returned source URL shapes, not just job counts. Workday list links can require detail enrichment; malformed salary data can prevent that enrichment.
3. Inspect the endpoint used by the normal page. Eightfold tenants differ between `pcsx/search` and `apply/v2/jobs`; branded portals can also move without their old URLs redirecting.
4. Use stable attributes for browser recipes and allow only the required official asset hosts. Block needs its CDN; newer Phenom layouts use `data-ph-at-id` instead of older CSS classes.
5. Check logos visually on the actual card background. HTTP 200 does not establish correct branding or contrast.
6. Keep unavailable and partial states explicit. A location-filtered empty result or parser failure does not mean an employer stopped hiring.

## Publication

GitHub main triggers the existing validation/build and GitHub Pages publication workflow. The Sites preset page consumes that catalog, so this catalog-only update needs no separate Sites code deployment. Human browsers and agent clients receive the same versioned artifacts and integrity hashes. The complete selection remains within the 200-ID limit.
