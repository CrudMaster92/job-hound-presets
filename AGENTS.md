# Job Hound Preset Agent Guide

This repository is the public source and GitHub Pages catalog for portable
JobHound company monitors. Read this file and `CONTRIBUTING.md` before changing
catalog data. A preset task is scoped to this repository; do not edit the
JobHound application or marketing site unless the user explicitly asks.

## Canonical source model

- The public endpoint is `api/v1/catalog.json`, but it publishes
  `catalog_version: 3`. Consumers follow its same-origin relative paths and
  SHA-256 hashes.
- Author company identity and facets only in
  `companies/<company-id>/company.json`.
- Author each scraper only once in
  `companies/<company-id>/monitors/<monitor-id>.json`. Keep IDs stable and
  increment `revision` whenever scraper behavior changes.
- Add collection membership only by reference in `collections/<id>.json`. One
  company or monitor may belong to several collections; never copy its recipe.
- `scripts/build_catalog.py` owns generated catalogs, search pages, member
  pages, API company/monitor artifacts, bundles, and `dist`. Never hand-edit or
  include generated output in a contribution unless a maintainer explicitly
  requests a release artifact.
- The version-1 preset schema exists only for importing old user-created files.
  Do not create root `catalog.json` files or `presets/<collection>.json`
  monoliths.
- Public install actions use `jobhound-catalog-install` version 1 as defined by
  `schemas/jobhound-catalog-install-v1.schema.json`. Keep handoffs bounded to
  200 stable company/monitor IDs and revisions. Never embed recipes, trust a
  browser-supplied path or hash, or install without JobHound resolving the
  current trusted catalog and asking for local confirmation.
- The GitHub Pages browser is a live catalog consumer. Keep preset collections
  primary, company search secondary, individual monitor selection available,
  and all referenced artifacts hash-checked before presenting an install.

## Scraper contribution rules

1. Start from current `main`. Reuse an existing company identity before adding
   one, and inspect a current company, monitor, schema, and collection example.
2. Keep a normal new-company change narrow: one company file, one monitor file,
   and the relevant collection reference/revision. Do not mix trackers,
   unrelated scrapers, app changes, or generated artifacts into the PR.
3. Use only public HTTPS sources and deterministic recipes. Prefer an official
   ATS/API, then HTML or JSON-LD, then bounded browser automation. Every request
   host must be in `allowed_hosts`; credentials, cookies, authorization headers,
   personal criteria, schedules, and local user data are forbidden.
4. Prove ownership, not just schema validity. Run the recipe through the real
   JobHound runtime and inspect titles and source URLs for cross-company
   contamination. A shared parent ATS feed must exclude unrelated employers.
   Use case-insensitive `source_filter.title_contains_any` only when titles
   contain a reliable company marker; filtering occurs after list
   normalization and before detail enrichment.
5. Report live evidence in the PR: strategy, job count, pages, completeness,
   warnings, representative source URLs, and validation time. Counts are a
   point-in-time observation, never a permanent expectation.
6. Mark a monitor `verified` only after a fresh live run returns at least one
   valid, company-owned job. If network access is unavailable, use honest
   `unverified` state with null evidence. A 404, sign-in wall, talent-community
   form, guessed ATS slug, or company page without public listings is blocked;
   do not fabricate a monitor or collection membership.
7. Mark bounded or incomplete feeds honestly, including
   `metadata.partial_listing`, so unseen jobs are not incorrectly closed.
8. Do not merge, close, comment on, approve, or mark a PR ready unless the user
   explicitly authorizes that action. A structurally valid but untested scraper
   remains a draft or needs repair.

## Required checks

Run these from the repository root:

```powershell
python scripts/validate_presets.py
python scripts/build_catalog.py
python -m unittest discover -s tests
```

Treat the build as a validation step and review its diff; do not commit generated
churn. Reviewers should reject duplicate identities or recipes, unstable IDs,
unsafe hosts, stale or invented verification, contamination, direct generated
edits, and changes based on an outdated branch.
