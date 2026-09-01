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
- `scripts/build_catalog.py` validates those sources and generates catalog
  version 3: compact indexes, paged collection membership, one artifact per
  company and monitor, and optional self-contained bundles.
- `schemas/jobhound-preset-v1.schema.json` remains available for importing old
  user-created version 1 files. The public catalog no longer has a monolithic
  authored preset.

The app currently accepts `ashby`, `greenhouse`, `lever`, `smartrecruiters`, `workday`, `jobvite`, `json_ld`, `generic_json`, `generic_html`, and `playwright` recipes. Recipe request hosts must appear in `allowed_hosts`, credential-bearing headers are forbidden, company keys and careers URLs must be unique, and each recipe's `careers_url` must match its company.

## Use the catalog

Consumers should fetch `api/v1/catalog.json`, require catalog version 3, and
resolve only the relative hashed paths it publishes. Collection membership and
search data are paged; recipes appear only in `monitors/<id>.json`. Optional
large bundles are for explicit download, not ordinary browsing or installation.

The [GitHub Pages catalog](https://crudmaster92.github.io/job-hound-presets/) is
an install-first catalog with preset cards, per-company and per-monitor
selection, and advanced company search. Its **Open in JobHound** action sends a
bounded, versioned selection to the loopback-only app; JobHound resolves and
hash-checks the trusted catalog again and requires a local confirmation before
installing anything. The handoff contains only stable IDs and revisions, never
recipes or personal data. Run
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
