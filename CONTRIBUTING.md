# Contributing a preset

1. Copy `templates/jobhound-preset.template.json` into `presets/<preset-id>.json`.
2. Keep the manifest ID and filename aligned. IDs and company keys use lowercase letters, numbers, and hyphens only.
3. Include only public HTTP(S) careers sources and deterministic recipes. Do not include credentials, cookies, authorization headers, personal criteria, schedules, or user data.
4. Make each company `careers_url` exactly match its recipe `careers_url`. Every recipe request hostname must be listed in `allowed_hosts`.
5. Add one catalog entry with the same ID, path, name, description, tags, and company count.
6. Run `python scripts/validate_presets.py` and include the result in your pull request.

Preset changes should be reviewable on their own. Avoid combining catalog work with website or application code. Maintainers may reject recipes that depend on private endpoints, authentication, excessive response sizes, or brittle selectors.
