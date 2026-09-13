# Recruitment additions, September 13, 2026

Adds three missing recruitment employers to collection revision 4: Staffmark Group, Beacon Hill and Kforce. The collection now contains 31 companies, 24 verified monitors and the same seven unavailable companies. Existing IDs and recipes are unchanged.

| Company | Runtime strategy | Jobs | Pages | Coverage |
|---|---|---:|---:|---|
| Staffmark Group | generic_html | 86 | 1 | Internal roles across group brands; listing descriptions included |
| Beacon Hill | generic_html | 10 | 1 | Initial US internal sales/recruiting listing; no descriptions |
| Kforce | playwright | 20 | 1 | Initial corporate result page; no descriptions |

These are point-in-time live observations through the canonical JobHound `ScraperRecipe` and `run_scraper`. All results have unique HTTPS source URLs. Each monitor explicitly sets `partial_listing=true`; the runtime returned `complete=false`. This preserves unseen jobs when a bounded source is checked. Counts, timestamps, representative normalized jobs, warnings and official ownership links are in `recruitment-additions-2026-09-13.json`.

Staffmark's dedicated internal page describes jobs supporting its own branches and clients. The identity is Staffmark Group because the feed covers internal group roles, not just one brand. Its listing excerpts occasionally contain malformed punctuation and source locations can contain inconsistent ZIP codes; preserve the source rather than guess a correction.

Beacon Hill's corporate careers page links directly to the dedicated internal board. The selected desktop listing avoids duplicate mobile cards and the general client-placement board. Some titles contain malformed source punctuation. Full-description and exhaustive pagination coverage remain unavailable in this recipe, as explicitly disclosed.

Kforce's corporate careers page links to its Taleo board. Rendered rows provide real job-detail URLs and stable requisition-derived IDs (for example `job221532` corresponds to application `reqNo=221532`), rather than positional row identifiers. Only the official host is allowed. The observed roles are internal talent and client executives and talent acquisition specialists.

Employbridge and Express were also investigated but are not added in this release. Employbridge's public JSON response has IDs without directly mappable detail URLs, and its desktop HTML uses positional IDs. Express's current Paycom cards use an outer link that the existing generic HTML adapter cannot select as its own descendant. Both need further recipe work or a separately scoped application capability before release; no access controls were bypassed and no placeholder monitors were created.

No local monitors were installed and no application code or personal data changed.

Validation: normalized catalog build passed (392 companies, 380 monitors overall); all eight repository tests passed; the application bundle contract accepted all 24 recruitment monitors; git diff --check passed.
