# Contributing catalog data

1. Reuse an existing `companies/<id>` identity before creating one. Aliases do
   not create another company, and membership in another collection never
   duplicates a monitor.
2. Put scraper behavior only in `companies/<id>/monitors/<monitor-id>.json`.
   IDs are permanent. Increase `revision` whenever recipe behavior changes;
   do not mutate an old revision merely to force clients to update.
   Do not edit generated catalogs, bundles, legacy monoliths, or copy recipes
   into collection files.
3. Include only public HTTPS careers sources and deterministic recipes. Never
   include credentials, cookies, authorization headers, personal criteria,
   schedules, or user data. Every request host must be explicit in
   `allowed_hosts`.
4. Prefer official ATS/API endpoints, then server-rendered HTML/JSON-LD, then a
   bounded browser recipe. Do not bypass access controls. Mark bounded feeds
   with `metadata.partial_listing: true` so unseen roles are not closed.
5. Record honest verification state, timestamp, observed job count, and
   warnings. A collection may include degraded or unverified coverage only
   when the limitation is visible and useful; never invent a centralized board.
6. Create `collections/<id>.json` using references, ranks/notes where relevant,
   structured facets, and optional suggested criteria. Suggestions are labels,
   not changes to a user's JobHound search profile.
7. Run both validators and include their results in the pull request:

```sh
python scripts/validate_presets.py
python scripts/build_catalog.py
```

Reviewers should reject duplicate identities, copied recipes, unstable IDs,
private endpoints, unexplained browser automation, excessive response sizes,
unsafe hosts, stale verification claims, or generated `dist` edits that do not
match the authored sources.

## Contribution-first PRs

Only contribute when your own human explicitly asks. Start from current main and inspect company IDs, existing ATS mappings and open PRs. One normalized monitor proposal per PR. New platforms need a separate runtime-support proposal; do not install plugins or edit generated runtime.

Use JobHound's five contribution tools (or its Contribute a company page) to preview and prepare the package. It includes companies/<id>/company.json, monitors/<id>.json, optional collection membership, and contributions/<monitor-id>/proposal.json with exact base_commit, a dated trimmed public fixture and employer ownership evidence. Leave authored verification unverified. A contributor's offline parsing or own network test is not the trusted gate.

The Trusted scraper validation lane reads candidate git JSON objects; only main's validator, dependencies and canonical exported runtime execute. It rejects unrelated/code/link changes and performs bounded live validation. Its separate publisher stores a receipt on review-receipts, tied to exact PR/base/head, recipe/proposal/runtime hashes and outcome. Jo reviews employer ownership and merges; agents never auto-merge. Eligible sources enter the next successful scheduled collection without a second feed-lock PR. Missing/failed receipts retain previous working pins.

Repository maintainers must protect main with the trusted validate and receipt checks, and restrict review-receipts writes to Jo and the trusted publisher. Do not activate this lane without that deployment control. Infrastructure/workflow edits are a separate Jo-reviewed change and cannot pass as recipe-only JSON. The validation runtime is generated from canonical JobHound; export it again rather than editing it here. The schemas/ directory remains authoritative for catalog formats; generated runtime schema snapshots must match it exactly.

Human GitHub OAuth/write approval belongs to the agent host. Never request tokens in chat, bypass approval cards or promise unobserved connector tools. Keep personal data out of every public file. Ready and merged are not published; inspect actual feed source hashes. Dated provisional findings can be shown only to the requesting human, labelled unvalidated and absent from the curated feed.

Security basis: [GitHub's pull_request_target documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target). Never execute candidate code in this privileged context.
