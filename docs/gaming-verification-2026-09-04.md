# Gaming scraper and logo verification — 2026-09-04

Gaming Industry expanded from 3 to **34 companies**, with **40 deterministic monitors** returning **2,568 listings** in the live verification runs. Sony / PlayStation and Nintendo are included. All **34 remote company logos loaded successfully in Chromium** (68 images across light/dark checks). Counts are point-in-time source listings, not a promise of active vacancies or a deduplicated worldwide inventory.

The normalized source catalog is updated locally at collection revision 4. Nothing was pushed, published, or installed into personal monitors. Existing unrelated Fortune-company changes and JobHound user data were preserved.

## Coverage

| Company | Monitors | Listings | Source strategies |
|---|---:|---:|---|
| 2K | 1 | 117 | generic_json |
| Activision | 1 | 83 | workday |
| Bandai Namco | 1 | 4 | generic_json |
| Behaviour Interactive | 1 | 36 | playwright |
| Blizzard Entertainment | 1 | 36 | workday |
| Bungie | 1 | 2 | greenhouse |
| Capcom | 1 | 2 | jobvite |
| CD PROJEKT RED | 1 | 43 | generic_json |
| Digital Extremes | 1 | 4 | generic_html |
| Eidos-Montréal | 1 | 4 | generic_html |
| Electronic Arts | 1 | 334 | generic_html |
| Epic Games | 1 | 162 | greenhouse |
| Frontier Developments | 1 | 14 | lever |
| Gameloft | 1 | 43 | generic_json |
| IO Interactive | 1 | 1 | generic_json |
| King | 1 | 16 | workday |
| Larian Studios | 1 | 69 | lever |
| Nintendo | 1 | 51 | generic_json |
| Paradox Interactive | 1 | 20 | generic_json |
| Remedy Entertainment | 1 | 4 | generic_json |
| Riot Games | 1 | 161 | greenhouse |
| Roblox | 1 | 226 | greenhouse |
| Rockstar Games | 1 | 66 | generic_json |
| Scopely | 1 | 183 | greenhouse |
| SEGA | 1 | 29 | generic_html |
| Sony Interactive Entertainment / PlayStation | 6 | 282 | greenhouse |
| Square Enix | 2 | 9 | generic_json |
| Supercell | 1 | 44 | ashby |
| Take-Two Interactive | 1 | 40 | generic_json |
| Ubisoft | 1 | 285 | generic_json |
| Unity | 1 | 124 | workday |
| Valve | 1 | 25 | generic_html |
| Warner Bros. Games | 1 | 1 | generic_json |
| Zynga | 1 | 48 | greenhouse |

## Material limits

- Regional emphasis is North America and Europe. Nintendo covers its North American board; Square Enix has separate America/Europe monitors; Bandai Namco and Capcom cover their U.S. boards. This is not every employer or regional board in the global gaming industry.
- PlayStation includes the global SIE board and five additional studio boards. Haven uses its English board to avoid the duplicate French postings. Bungie remains its own identity. SEGA Europe already includes Creative Assembly and Sports Interactive, so separate duplicate monitors were not added.
- Warner Bros. Games remains explicitly **partial/degraded**: one role from the strict WB Games title filter. Its recipe now prevents unseen roles being treated as closed.
- Epic’s public Greenhouse feed works, but its detail host returned HTTP 403 to automated checks. Roblox’s feed works, but its detail host timed out. No access controls were bypassed.
- Ubisoft, CD PROJEKT RED and Gameloft use complete compact public feeds with human job URLs. These feeds omit descriptions; keyword matching against descriptions is therefore unavailable. Several other HTML sources also provide listing details only.
- Valve and some studio boards include standing/open applications. Teamtailor multi-office jobs retain the primary city in the normalized location and other offices in their description.
- KRAFTON’s corporate page blocked automated access and was not promoted as a fabricated working monitor. It is outside this 34-company collection.
- Logos are live external assets. They can change or fail later; existing initials fallbacks remain in place. Several monochrome marks have lower contrast on dark backgrounds; the shared collection logo tiles use white backgrounds.

## Useful patterns for scale

1. **Start with the official careers site, then identify its public ATS feed.** Greenhouse, Lever, Workday, SmartRecruiters and Ashby patterns cover most employers. Teamtailor’s public `/jobs.json` feed avoids browser pagination and supplies descriptions.
2. **Test links as well as job counts.** Nintendo’s feed supplied homepage links; stable IDs now resolve to actual job pages. Jobvite needed its own host as the link base. Workday needs detail enrichment to replace relative paths with usable role URLs; current boards fit within the 250-detail bound.
3. **Audit identity and pagination.** EA reused HTML row IDs across pages, silently collapsing 334 roles into 20. Selecting the record header without the positional ID preserves stable URL-derived IDs. Behaviour’s browser recipe now traverses all four pages and returns 36 roles.
4. **Use narrow declarative fallbacks.** Several Greenhouse boards return null optional fields that the current native adapter does not tolerate. A typed generic JSON mapping avoids that issue without application changes. SmartRecruiters’ `ref` is an API endpoint; resolving its numeric ID against the public company board gives human job links.
5. **Keep one company identity and distinct board ownership.** Add regional/studio monitors only where needed, and reference them from collections. Omit duplicate language boards and document parent-company coverage.
6. **Logo HTTP 200 is insufficient.** Decode the file, inspect the brand, and embed its remote URL in a real browser. This caught game artwork, social icons, faint branding, and a Unity favicon that downloaded successfully but failed in the browser.

## Validation

- All 40 promoted recipes passed the canonical JobHound `ScraperRecipe` model and live `run_scraper` execution; promotion requires an exact SHA-256 match to the tested recipe.
- Every returned role has an HTTPS source URL. First/middle/last role links were sampled for each monitor; JavaScript-only pages may not expose their title in the raw HTTP response. Epic and Roblox detail-check limitations remain explicit.
- All 259 returned Workday records across Activision, Blizzard, King and Unity have company-board job paths after detail enrichment.
- Full catalog schema/build: **98 companies, 107 monitors, 3 collections** (includes unrelated existing work). Repository tests: **4 passed**. `git diff --check` passed.
- No application/UI/MCP code changed; all recipes use the existing shared runtime and catalog contracts.

Technical URL note: JobHound strips trailing slashes from careers URLs. Nintendo and the compact SmartRecruiters recipes use the standards-equivalent directory URL ending in `/.` so relative numeric IDs retain the correct directory when normalized. These URLs and representative resulting job links were fetched successfully.

The accompanying `gaming-verification-2026-09-04.json` records each monitor’s revision, strategy, count, warnings, tested recipe hash, and representative URLs.
