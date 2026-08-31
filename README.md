# Job Hound Presets

Public, portable company-monitor presets for [Job Hound](https://job-hound.realperson.chatgpt.site).

Each preset is a strict JSON manifest containing public careers URLs and deterministic scraper recipes. A Job Hound user can inspect a preset, select individual companies, and install those monitors while keeping their own global cities, titles, keywords, and schedule. Presets never contain credentials or personal search data.

## Repository contract

Authored data is normalized so a scraper is maintained once and reused by any
number of collections:

- `companies/<company-id>/company.json` owns identity, aliases, industries,
  specialties, and discovery tags.
- `companies/<company-id>/monitors/<monitor-id>.json` owns one versioned,
  deterministic scraper recipe and its latest verification result. A company
  may have multiple monitors when it genuinely has separate careers systems.
- `collections/<collection-id>.json` references companies and, optionally,
  specific monitor IDs. Collections own ranking, industry, role, and location
  facets plus optional suggested JobHound criteria; they never duplicate a
  recipe or silently change a user's filters.
- `scripts/build_catalog.py` validates those sources and generates the stable
  `api/v1/catalog.json`, company details, collection details, and self-contained
  downloadable `jobhound-preset` version 2 bundles.
- `presets/*.json` and `schemas/jobhound-preset-v1.schema.json` remain the
  compatible version 1 import format.

The app currently accepts `ashby`, `greenhouse`, `lever`, `smartrecruiters`, `workday`, `jobvite`, `json_ld`, `generic_json`, `generic_html`, and `playwright` recipes. Recipe request hosts must appear in `allowed_hosts`, credential-bearing headers are forbidden, company keys and careers URLs must be unique, and each recipe's `careers_url` must match its company.

## Use the catalog

Consumers should fetch `api/v1/catalog.json`, require catalog version 2, then
resolve only the relative `path` or `download_path` published by that catalog.
Download bytes are canonicalized and SHA-256 hashed in the catalog. JobHound
caches the last known good catalog for offline use, validates a selected bundle,
and validates every installed or updated scraper before activation.

The [GitHub Pages catalog](https://crudmaster92.github.io/job-hound-presets/) is
also a human-readable catalog with search and structured filters. Run
`python scripts/build_catalog.py` and open `dist/index.html` to preview it
locally.

## Contribute

Add or update normalized company, monitor, and collection sources; use stable
lowercase hyphenated IDs, include only public sources, and run:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_presets.py
python scripts/build_catalog.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the review checklist. This repository is licensed under the MIT License; company names and trademarks remain the property of their respective owners.
