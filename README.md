# Job Hound Presets

Public, portable company-monitor presets for [Job Hound](https://job-hound.realperson.chatgpt.site).

Each preset is a strict JSON manifest containing public careers URLs and deterministic scraper recipes. A Job Hound user can inspect a preset, select individual companies, and install those monitors while keeping their own global cities, titles, keywords, and schedule. Presets never contain credentials or personal search data.

## Repository contract

- `catalog.json` is the stable machine-readable entry point.
- `presets/*.json` contains installable `jobhound-preset` version 1 manifests.
- `schemas/jobhound-preset-v1.schema.json` describes the official app contract.
- `templates/jobhound-preset.template.json` is the starting point for a contribution.
- `scripts/validate_presets.py` validates every catalog entry and manifest.

The app currently accepts `ashby`, `greenhouse`, `lever`, `smartrecruiters`, `workday`, `jobvite`, `json_ld`, `generic_json`, `generic_html`, and `playwright` recipes. Recipe request hosts must appear in `allowed_hosts`, credential-bearing headers are forbidden, company keys and careers URLs must be unique, and each recipe's `careers_url` must match its company.

## Use the catalog

Consumers should fetch `catalog.json`, check `catalog_version`, then fetch a manifest by its relative `path`. Validate the manifest before offering it for installation. A catalog listing is not proof that every third-party careers page is currently healthy; Job Hound still validates and runs each selected scraper after installation.

## Contribute

Copy the template, use a lowercase hyphenated ID, include only public sources, and run:

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_presets.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the review checklist. This repository is licensed under the MIT License; company names and trademarks remain the property of their respective owners.
