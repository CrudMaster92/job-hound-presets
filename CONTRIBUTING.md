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
